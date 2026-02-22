# rag service — langchain-powered retrieval augmented generation
# embeds queries, runs mongodb atlas vector search, generates answers with gemini
#
# retrieval pipeline:
#   1. embed user query using sentence-transformers
#   2. mongodb atlas $vectorSearch on rag_vectors collection
#   3. re-rank results by cosine similarity score
#   4. build context from top-k retrieved documents
#   5. generate answer using gemini with source citations
#   6. return results + generated answer

import asyncio
import logging
from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.config import settings
from app.services.db import Database

logger = logging.getLogger(__name__)

# max conversation history turns sent to the llm
MAX_HISTORY_TURNS = 10

# singleton embedding model (loaded once)
_embedding_model: Optional[HuggingFaceEmbeddings] = None


def get_embedding_model() -> HuggingFaceEmbeddings:
    """get or create the singleton embedding model"""
    global _embedding_model
    if _embedding_model is None:
        logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
        _embedding_model = HuggingFaceEmbeddings(
            model_name=settings.EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
        logger.info("Embedding model loaded")
    return _embedding_model


def get_llm() -> ChatGoogleGenerativeAI:
    """create a gemini llm instance for answer generation"""
    return ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        google_api_key=settings.GEMINI_API_KEY,
        temperature=0.3,
        max_output_tokens=4096,
    )


# rag prompt template — clinical assistant: helps therapists form assessments

RAG_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a clinical assistant for licensed therapists on the CalmAI platform.
You are speaking to a licensed professional — be direct, thorough, and clinically useful.

YOUR JOB:
- Answer the therapist's question as fully and helpfully as possible
- Synthesize information from the retrieved patient journals and therapy conversations
- Identify patterns, recurring themes, severity indicators, and changes over time
- When relevant, share clinical perspectives, known therapeutic approaches, and considerations from the knowledge base
- Reference specific sources by type and date so the therapist can verify
- Use clear sections and bullet points for readability
- If the retrieved data is insufficient, say what's missing and suggest follow-up questions

TONE:
- Be a knowledgeable colleague, not a disclaimer machine
- Give substantive, actionable information — the therapist will use their own clinical judgment
- End with a brief note: this is retrieved information to support your clinical reasoning, not a substitute for your professional judgment
- If content suggests crisis or self-harm, flag it prominently"""),
    ("human", """Based on the following retrieved documents, answer the therapist's question.

RETRIEVED DOCUMENTS:
{context}

{history_block}QUESTION: {query}

Provide a thorough, well-structured answer. Be direct and clinically useful."""),
])

# prompt for follow-up questions (includes conversation history)
FOLLOW_UP_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a clinical assistant for licensed therapists on the CalmAI platform.
You are in an ongoing conversation with a therapist. Build on what was already discussed.

YOUR JOB:
- Answer the follow-up question directly and thoroughly
- Build on the previous discussion — avoid repeating what was already covered
- Incorporate newly retrieved documents alongside the conversation context
- Share clinical perspectives, therapeutic considerations, and relevant patterns
- Reference specific sources by type and date
- If no new relevant documents were found, work with the existing conversation context

TONE:
- Be a knowledgeable colleague, not a disclaimer machine
- Give substantive, actionable information — the therapist will use their own clinical judgment
- End with a brief note when appropriate: this is to support your reasoning, not replace it
- If content suggests crisis or self-harm, flag it prominently"""),
    ("human", """CONVERSATION HISTORY:
{history_block}

NEW RETRIEVED DOCUMENTS:
{context}

FOLLOW-UP QUESTION: {query}

Provide a thorough answer building on the conversation. Be direct and clinically useful."""),
])

# answer generation chains
_chain = None
_follow_up_chain = None
_router_chain = None
_general_chain = None


def get_rag_chain():
    """get or create the rag answer generation chain"""
    global _chain
    if _chain is None:
        llm = get_llm()
        _chain = RAG_PROMPT | llm | StrOutputParser()
    return _chain


def get_follow_up_chain():
    """get or create the follow-up answer generation chain"""
    global _follow_up_chain
    if _follow_up_chain is None:
        llm = get_llm()
        _follow_up_chain = FOLLOW_UP_PROMPT | llm | StrOutputParser()
    return _follow_up_chain


# lightweight intent router — classifies whether a query needs patient data
ROUTER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "You classify therapist queries. Respond with ONLY one word: RETRIEVE or GENERAL.\n"
     "RETRIEVE = needs patient journal data, specific patient info, or records.\n"
     "GENERAL = clinical knowledge question, therapeutic technique, general mental health info, or a greeting."),
    ("human", "{query}"),
])


def get_router_chain():
    """get or create the intent router chain (tiny, fast)"""
    global _router_chain
    if _router_chain is None:
        # use a low-token llm for classification
        router_llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0.0,
            max_output_tokens=10,
        )
        _router_chain = ROUTER_PROMPT | router_llm | StrOutputParser()
    return _router_chain


# prompt for general clinical knowledge questions (no retrieval)
GENERAL_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a clinical assistant for licensed therapists on the CalmAI platform.
The therapist is asking a general clinical knowledge question that does not require
patient-specific data. Answer helpfully using your clinical knowledge.

TONE:
- Be a knowledgeable colleague — direct and thorough
- Provide evidence-based information about therapeutic techniques, conditions, and approaches
- End with a brief note: this is general clinical knowledge to support your reasoning, not a substitute for your professional judgment
- If the question actually seems patient-specific, let the therapist know you can search their patient's records if they rephrase with a patient selected"""),
    ("human", """{history_block}QUESTION: {query}

Provide a thorough, clinically useful answer."""),
])


def get_general_chain():
    """get or create the general knowledge answer chain"""
    global _general_chain
    if _general_chain is None:
        llm = get_llm()
        _general_chain = GENERAL_PROMPT | llm | StrOutputParser()
    return _general_chain


async def classify_intent(query: str, has_patient_filter: bool) -> str:
    """classify whether a query needs retrieval or is a general knowledge question

    returns 'retrieve' or 'general'
    """
    try:
        chain = get_router_chain()
        result = await chain.ainvoke({"query": query})
        classification = result.strip().upper()
        if "GENERAL" in classification:
            logger.info(f"Query classified as GENERAL: {query[:60]}")
            return "general"
        logger.info(f"Query classified as RETRIEVE: {query[:60]}")
        return "retrieve"
    except Exception as e:
        logger.warning(f"Intent classification failed, defaulting to retrieve: {e}")
        return "retrieve"


async def vector_search(
    db: Database,
    query_embedding: list[float],
    top_k: int = 5,
    patient_id: Optional[str] = None,
    source_type: Optional[str] = None,
) -> list[dict]:
    """run mongodb atlas vector search on rag_vectors collection

    uses $vectorSearch aggregation stage with cosine similarity.
    supports optional filtering by patient_id and doc_type.
    """

    # build the vector search stage
    vector_search_stage = {
        "$vectorSearch": {
            "index": "vector_index",
            "path": "embedding",
            "queryVector": query_embedding,
            "numCandidates": top_k * 10,
            "limit": top_k,
        }
    }

    # add pre-filter if we have constraints
    filter_conditions = {}
    if patient_id:
        filter_conditions["patient_id"] = patient_id
    if source_type:
        filter_conditions["doc_type"] = source_type

    if filter_conditions:
        vector_search_stage["$vectorSearch"]["filter"] = filter_conditions

    # project the fields we need plus the search score
    project_stage = {
        "$project": {
            "content": 1,
            "doc_type": 1,
            "metadata": 1,
            "patient_id": 1,
            "journal_id": 1,
            "conversation_id": 1,
            "score": {"$meta": "vectorSearchScore"},
        }
    }

    pipeline = [vector_search_stage, project_stage]

    results = []
    try:
        cursor = db.rag_vectors.aggregate(pipeline)
        async for doc in cursor:
            results.append({
                "content": doc.get("content", ""),
                "doc_type": doc.get("doc_type", "unknown"),
                "metadata": doc.get("metadata", {}),
                "patient_id": doc.get("patient_id"),
                "score": doc.get("score", 0.0),
            })
        if results:
            logger.info(f"Vector search returned {len(results)} results")
        else:
            logger.warning("Vector search returned no results, falling back to text search")
            results = await _fallback_text_search(db, top_k, patient_id, source_type)
    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        # fallback to text search if vector search index is not available
        results = await _fallback_text_search(db, top_k, patient_id, source_type)

    return results


async def _fallback_text_search(
    db: Database,
    top_k: int,
    patient_id: Optional[str] = None,
    source_type: Optional[str] = None,
) -> list[dict]:
    """fallback text-based search when vector search index is unavailable"""
    query = {}
    if patient_id:
        query["patient_id"] = patient_id
    if source_type:
        query["doc_type"] = source_type

    logger.info(f"Fallback text search with query: {query}, limit: {top_k}")
    cursor = db.rag_vectors.find(query).limit(top_k)
    results = []
    async for doc in cursor:
        results.append({
            "content": doc.get("content", ""),
            "doc_type": doc.get("doc_type", "unknown"),
            "metadata": doc.get("metadata", {}),
            "patient_id": doc.get("patient_id"),
            "score": 0.5,  # no real score for fallback
        })
    logger.info(f"Fallback search returned {len(results)} results")
    return results


def _format_context(results: list[dict]) -> str:
    """format retrieved documents into a context string for the llm"""
    if not results:
        return "No relevant documents found."

    context_parts = []
    for i, result in enumerate(results, 1):
        doc_type = result.get("doc_type", "unknown")
        metadata = result.get("metadata", {})
        score = result.get("score", 0.0)

        # build source label
        if doc_type == "journal":
            patient_id = metadata.get("patient_id", result.get("patient_id", "unknown"))
            entry_date = metadata.get("entry_date", "unknown date")
            source = f"Journal entry (Patient: {patient_id}, Date: {entry_date})"
        elif doc_type == "conversation":
            conv_id = metadata.get("conversation_id", "unknown")
            source = f"Therapy conversation ({conv_id})"
        else:
            source = f"Document ({doc_type})"

        context_parts.append(
            f"[Source {i}] {source} (relevance: {score:.2f})\n{result['content']}"
        )

    return "\n\n---\n\n".join(context_parts)


def _extract_sources(results: list[dict]) -> list[str]:
    """extract source identifiers from results for the response"""
    sources = []
    for result in results:
        doc_type = result.get("doc_type", "unknown")
        metadata = result.get("metadata", {})

        if doc_type == "journal":
            patient_id = metadata.get("patient_id", result.get("patient_id", ""))
            entry_date = metadata.get("entry_date", "")
            sources.append(f"journal:{patient_id}:{entry_date}")
        elif doc_type == "conversation":
            conv_id = metadata.get("conversation_id", "")
            sources.append(f"conversation:{conv_id}")
        else:
            sources.append(f"{doc_type}:unknown")

    return sources


def _format_history(conversation_history: list[dict]) -> str:
    """format conversation history into a string block for the prompt"""
    if not conversation_history:
        return ""

    # limit to max turns
    history = conversation_history[-MAX_HISTORY_TURNS:]
    parts = []
    for msg in history:
        role_label = "Therapist" if msg.get("role") == "user" else "Assistant"
        parts.append(f"{role_label}: {msg.get('content', '')}")

    return "\n".join(parts)


async def search(
    db: Database,
    query: str,
    top_k: int = 5,
    patient_id: Optional[str] = None,
    source_type: Optional[str] = None,
    conversation_history: Optional[list[dict]] = None,
) -> dict:
    """full rag search pipeline — classify intent, optionally retrieve, generate answer

    routes queries through an intent classifier first:
    - general clinical questions → answered directly without retrieval
    - patient-specific questions → full retrieval pipeline
    """

    history = conversation_history or []
    has_history = len(history) > 0

    # 0. classify intent — skip retrieval for general knowledge questions
    intent = await classify_intent(query, has_patient_filter=bool(patient_id))

    if intent == "general" and not has_history:
        # answer directly without retrieval
        try:
            chain = get_general_chain()
            generated_answer = await chain.ainvoke({
                "query": query,
                "history_block": "",
            })
        except Exception as e:
            logger.error(f"General answer generation failed: {e}")
            generated_answer = "Unable to generate an answer. Please try again."

        return {
            "query": query,
            "results": [],
            "generated_answer": generated_answer,
            "sources": [],
        }

    if intent == "general" and has_history:
        # general follow-up — use conversation context, no new retrieval
        try:
            chain = get_general_chain()
            history_block = _format_history(history) + "\n\n"
            generated_answer = await chain.ainvoke({
                "query": query,
                "history_block": history_block,
            })
        except Exception as e:
            logger.error(f"General follow-up failed: {e}")
            generated_answer = "Unable to generate an answer. Please try again."

        return {
            "query": query,
            "results": [],
            "generated_answer": generated_answer,
            "sources": [],
        }

    # intent == "retrieve" — full rag pipeline

    # 1. embed the query
    embedding_model = get_embedding_model()
    query_embedding = embedding_model.embed_query(query)

    # 2. run vector search — pull journals and conversations separately
    #    so the model always gets context from both source types
    if source_type:
        # explicit filter: single search
        raw_results = await vector_search(
            db=db,
            query_embedding=query_embedding,
            top_k=top_k,
            patient_id=patient_id,
            source_type=source_type,
        )
    else:
        # no filter: fetch top_k journals + top_k conversations independently
        journal_results, conversation_results = await asyncio.gather(
            vector_search(
                db=db,
                query_embedding=query_embedding,
                top_k=top_k,
                patient_id=patient_id,
                source_type="journal",
            ),
            vector_search(
                db=db,
                query_embedding=query_embedding,
                top_k=top_k,
                patient_id=None,  # conversations aren't patient-scoped
                source_type="conversation",
            ),
        )
        raw_results = journal_results + conversation_results

    # 3. format results for response
    results = []
    for r in raw_results:
        metadata = r.get("metadata", {})
        # convert all metadata values to strings for the response model
        str_metadata = {k: str(v) for k, v in metadata.items() if v is not None}
        results.append({
            "content": r["content"],
            "score": round(r.get("score", 0.0), 4),
            "source": r["doc_type"],
            "metadata": str_metadata,
        })

    # 4. extract sources
    sources = _extract_sources(raw_results)

    # 5. generate answer using gemini via langchain
    generated_answer = None
    if raw_results:
        try:
            context = _format_context(raw_results)

            if has_history:
                # follow-up question with conversation context
                chain = get_follow_up_chain()
                history_block = _format_history(history)
                generated_answer = await chain.ainvoke({
                    "context": context,
                    "query": query,
                    "history_block": history_block,
                })
            else:
                # first question — no history
                chain = get_rag_chain()
                generated_answer = await chain.ainvoke({
                    "context": context,
                    "query": query,
                    "history_block": "",
                })
        except Exception as e:
            logger.error(f"Answer generation failed: {e}")
            generated_answer = (
                "Unable to generate a synthesized answer. "
                "Please review the retrieved sources below."
            )

    return {
        "query": query,
        "results": results,
        "generated_answer": generated_answer,
        "sources": sources,
    }
