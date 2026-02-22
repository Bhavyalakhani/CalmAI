# async mongodb client for the backend api
# uses motor for non-blocking operations

import logging
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import settings

logger = logging.getLogger(__name__)


class Database:
    """async mongodb connection manager"""

    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None

    async def connect(self):
        """establish connection to mongodb"""
        if self.client is not None:
            return

        logger.info(f"Connecting to MongoDB database: {settings.MONGODB_DATABASE}")
        self.client = AsyncIOMotorClient(settings.MONGODB_URI)
        self.db = self.client[settings.MONGODB_DATABASE]

        # verify connection
        await self.client.admin.command("ping")
        logger.info("MongoDB connection established")

    async def close(self):
        """close mongodb connection"""
        if self.client:
            self.client.close()
            self.client = None
            self.db = None
            logger.info("MongoDB connection closed")

    # collection accessors

    @property
    def users(self):
        return self.db["users"]

    @property
    def rag_vectors(self):
        return self.db["rag_vectors"]

    @property
    def conversations(self):
        return self.db["conversations"]

    @property
    def journals(self):
        return self.db["journals"]

    @property
    def incoming_journals(self):
        return self.db["incoming_journals"]

    @property
    def patient_analytics(self):
        return self.db["patient_analytics"]

    @property
    def pipeline_metadata(self):
        return self.db["pipeline_metadata"]

    @property
    def invite_codes(self):
        return self.db["invite_codes"]


# singleton instance
db = Database()


async def get_db() -> Database:
    """dependency injection for database access"""
    return db
