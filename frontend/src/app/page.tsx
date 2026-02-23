import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import {
  Brain,
  Shield,
  BookOpen,
  ArrowRight,
  Sparkles,
  Check,
  Activity,
  Search,
  BarChart3,
  MessageSquare,
  FileText,
  Zap,
  TrendingUp,
  Quote,
  Star,

} from "lucide-react";

// reusable cards

function FeatureCard({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="group relative flex flex-col gap-3 rounded-xl border bg-background p-6 transition-all duration-300 hover:border-foreground/20 hover:shadow-lg hover:shadow-foreground/[0.03] hover:-translate-y-0.5">
      <div className="flex h-10 w-10 items-center justify-center rounded-lg border bg-muted transition-colors group-hover:bg-foreground/10">
        {icon}
      </div>
      <h3 className="font-semibold">{title}</h3>
      <p className="text-sm leading-relaxed text-muted-foreground">
        {description}
      </p>
    </div>
  );
}

function StatBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col items-center gap-1 text-center">
      <span className="text-3xl font-bold tracking-tight">{value}</span>
      <span className="text-sm text-muted-foreground">{label}</span>
    </div>
  );
}

function StepCard({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="flex flex-col items-center gap-4 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl border-2 border-foreground/10 bg-muted">
        {icon}
      </div>
      <h3 className="font-semibold">{title}</h3>
      <p className="text-sm leading-relaxed text-muted-foreground">
        {description}
      </p>
    </div>
  );
}

function TestimonialCard({
  quote,
  name,
  role,
  stars,
}: {
  quote: string;
  name: string;
  role: string;
  stars: number;
}) {
  return (
    <div className="flex flex-col gap-4 rounded-xl border bg-background p-6">
      <div className="flex gap-0.5">
        {Array.from({ length: stars }).map((_, i) => (
          <Star key={i} className="h-4 w-4 fill-amber-400 text-amber-400" />
        ))}
      </div>
      <div className="flex gap-2">
        <Quote className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground/50" />
        <p className="text-sm leading-relaxed text-muted-foreground">{quote}</p>
      </div>
      <div className="mt-auto pt-2 border-t">
        <p className="text-sm font-medium">{name}</p>
        <p className="text-xs text-muted-foreground">{role}</p>
      </div>
    </div>
  );
}

// faq data

const faqs = [
  {
    question: "How does CalmAI keep patient data secure?",
    answer:
      "All data is encrypted in transit and at rest. CalmAI stores patient information in MongoDB Atlas with role-based access controls. Therapists only see their own patients, and patients can only access their own journals. No patient data is ever shared with third parties or used for model training.",
  },
  {
    question: "Does CalmAI make diagnoses or treatment recommendations?",
    answer:
      "Absolutely not. CalmAI is an information retrieval and organization tool. It surfaces patterns, trends, and specific journal entries - but every clinical decision stays with the therapist. All AI-generated responses include source citations so you can verify every claim.",
  },
  {
    question: "How long does it take to get started?",
    answer:
      "Minutes. Create your therapist workspace, generate an invite code, and share it with your patients. Once they sign up and start journaling, entries are processed automatically. Your analytics dashboard populates as data flows in.",
  },
  {
    question: "What kind of insights does the analytics dashboard show?",
    answer:
      "The dashboard shows topic distribution across patient journals, how themes evolve over time, writing frequency patterns, representative entries for each topic, and comparative analytics across your entire practice. All powered by BERTopic models trained on your data.",
  },
  {
    question: "Can patients see the analytics or AI-generated insights?",
    answer:
      "No. The analytics dashboard, topic modeling, and RAG search are exclusively available to therapists. Patients have a separate, minimal interface focused on journaling and responding to prompts.",
  },
];

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      {/* nav */}
      <header className="sticky top-0 z-50 border-b bg-background/80 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <Link href="/" className="flex items-center gap-2">
            <Brain className="h-6 w-6" />
            <span className="text-lg font-bold tracking-tight">CalmAI</span>
          </Link>
          <nav className="flex items-center gap-2">
            <Button variant="ghost" size="sm" asChild>
              <Link href="/login">Log in</Link>
            </Button>
            <Button size="sm" asChild>
              <Link href="/signup">Get Started</Link>
            </Button>
          </nav>
        </div>
      </header>

      {/* hero */}
      <main className="flex flex-1 flex-col">
        <section className="relative mx-auto flex max-w-4xl flex-col items-center gap-8 px-6 pb-24 pt-28 text-center">
          <div className="inline-flex items-center gap-2 rounded-full border px-4 py-1.5 text-sm text-muted-foreground">
            <Sparkles className="h-3.5 w-3.5" />
            Built for licensed therapists
          </div>

          <h1 className="relative text-5xl font-bold leading-[1.1] tracking-tight sm:text-6xl">
            {/* animated glow behind the entire headline */}
            <span
              className="pointer-events-none absolute -inset-8 -z-10 rounded-3xl opacity-60 blur-3xl"
              style={{
                background:
                  "radial-gradient(ellipse 80% 60% at 50% 45%, hsl(var(--foreground) / 0.15), hsl(var(--foreground) / 0.06), transparent 70%)",
              }}
            />
            <span
              className="pointer-events-none absolute -inset-16 -z-20 rounded-full opacity-40 blur-[80px]"
              style={{
                background:
                  "radial-gradient(circle at 50% 50%, hsl(var(--foreground) / 0.12), transparent 60%)",
              }}
            />
            Clinical intelligence
            <br />
            <span className="text-muted-foreground">without the noise</span>
          </h1>

          <p className="max-w-2xl text-lg text-muted-foreground">
            Stop digging through months of session notes to find the pattern you
            know is there. CalmAI organizes patient journals, discovers emerging
            themes, and retrieves the exact evidence you need - so you can focus
            on what matters most.
          </p>

          <div className="flex gap-3">
            <Button size="lg" asChild>
              <Link href="/signup">
                Start free trial
                <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
            <Button size="lg" variant="outline" asChild>
              <Link href="/login">Log in</Link>
            </Button>
          </div>

          {/* trust indicators */}
          <div className="mt-4 flex flex-wrap items-center justify-center gap-6 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5"><FileText className="h-3.5 w-3.5" /> Source-cited answers</span>
            <span className="flex items-center gap-1.5"><Shield className="h-3.5 w-3.5" /> No diagnostic outputs</span>
            <span className="flex items-center gap-1.5"><Zap className="h-3.5 w-3.5" /> Sub-second retrieval</span>
          </div>
        </section>

        {/* how it works */}
        <section className="border-t bg-muted/20">
          <div className="mx-auto max-w-5xl px-6 py-20">
            <div className="mb-12 text-center">
              <h2 className="text-3xl font-bold tracking-tight">How it works</h2>
              <p className="mt-2 text-sm text-muted-foreground">
                From patient journal entry to therapist insight in minutes
              </p>
            </div>
            <div className="grid gap-12 sm:grid-cols-3">
              <StepCard
                icon={<FileText className="h-6 w-6" />}
                title="Capture"
                description="Patients write freely in a private, distraction-free interface. Each entry is timestamped and securely stored."
              />
              <StepCard
                icon={<BarChart3 className="h-6 w-6" />}
                title="Analyze"
                description="BERTopic models automatically discover themes, track trends over time, and generate per-patient analytics."
              />
              <StepCard
                icon={<Search className="h-6 w-6" />}
                title="Retrieve"
                description="Ask questions in plain English and get answers grounded in real patient data - every claim is cited and verifiable."
              />
            </div>
          </div>
        </section>

        {/* platform capabilities */}
        <section className="border-t">
          <div className="mx-auto max-w-6xl px-6 py-24">
            <div className="mb-12 text-center">
              <h2 className="text-3xl font-bold tracking-tight">
                Everything a clinical team needs
              </h2>
              <p className="mt-2 text-sm text-muted-foreground">
                Purpose-built tools for organizing and reasoning over patient journal data
              </p>
            </div>
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              <FeatureCard
                icon={<BookOpen className="h-5 w-5" />}
                title="Patient Journaling"
                description="A private space where patients write freely. Entries flow directly into your analytics dashboard - zero manual data entry."
              />
              <FeatureCard
                icon={<Brain className="h-5 w-5" />}
                title="RAG-Powered Search"
                description="Ask questions in plain English, get answers grounded in real patient data. Every response includes source citations."
              />
              <FeatureCard
                icon={<Shield className="h-5 w-5" />}
                title="Clinician-First Design"
                description="No diagnoses. No treatment plans. CalmAI surfaces evidence and patterns - you make the clinical decisions."
              />
              <FeatureCard
                icon={<TrendingUp className="h-5 w-5" />}
                title="Topic Trend Analysis"
                description="Watch themes emerge and evolve month by month. Catch early warning signs before they escalate."
              />
              <FeatureCard
                icon={<MessageSquare className="h-5 w-5" />}
                title="Conversation Corpus"
                description="3,500+ indexed counseling exchanges with topic and severity labels. Search by keyword or browse by category."
              />
              <FeatureCard
                icon={<Activity className="h-5 w-5" />}
                title="Per-Patient Analytics"
                description="Topic breakdowns, writing frequency, and representative entries for every patient - all one click away."
              />
            </div>
          </div>
        </section>

        {/* stats */}
        <section className="border-t bg-muted/40">
          <div className="mx-auto grid max-w-4xl grid-cols-2 gap-8 px-6 py-20 sm:grid-cols-4">
            <StatBlock label="Conversations indexed" value="3,500+" />
            <StatBlock label="Journal entries" value="1,000+" />
            <StatBlock label="Average query time" value="< 1s" />
            <StatBlock label="RAG faithfulness" value="90%+" />
          </div>
        </section>

        {/* testimonials */}
        <section className="border-t">
          <div className="mx-auto max-w-6xl px-6 py-20">
            <div className="mb-12 text-center">
              <Badge variant="secondary" className="mb-4">Testimonials</Badge>
              <h2 className="text-3xl font-bold tracking-tight">
                Trusted by therapists who care about evidence
              </h2>
              <p className="mt-2 text-sm text-muted-foreground">
                See why clinicians are switching to CalmAI for patient journal analysis
              </p>
            </div>
            <div className="grid gap-6 sm:grid-cols-3">
              <TestimonialCard
                stars={5}
                quote="I used to spend hours cross-referencing session notes. CalmAI surfaces the patterns I need in seconds. It has genuinely changed how I prepare for sessions."
                name="Dr. Maya Rodriguez"
                role="Clinical Psychologist"
              />
              <TestimonialCard
                stars={5}
                quote="The fact that every AI response comes with citations gives me confidence. I can verify every claim against the original journal entries before making any clinical decision."
                name="Dr. James Liu"
                role="Licensed Therapist, LMFT"
              />
              <TestimonialCard
                stars={5}
                quote="Onboarding was seamless. Our team was up and running in under ten minutes. The patient invite code system is brilliantly simple."
                name="Sarah Kim"
                role="Practice Manager, Mindful Health Group"
              />
            </div>
          </div>
        </section>

        {/* pricing */}
        <section className="border-t bg-muted/20">
          <div className="mx-auto max-w-6xl px-6 py-20">
            <div className="mb-10 text-center">
              <h2 className="text-3xl font-bold tracking-tight">Pricing</h2>
              <p className="mt-2 text-sm text-muted-foreground">
                Transparent plans for solo practitioners and clinical teams
              </p>
            </div>
            <div className="grid gap-6 sm:grid-cols-3">
              <div className="flex flex-col rounded-xl border bg-background p-6">
                <p className="text-sm text-muted-foreground">Starter</p>
                <p className="mt-2 text-3xl font-bold">$49</p>
                <p className="text-xs text-muted-foreground">per clinician / month</p>
                <ul className="mt-4 space-y-2 text-sm">
                  <li className="flex items-center gap-2"><Check className="h-4 w-4" /> Up to 100 active patients</li>
                  <li className="flex items-center gap-2"><Check className="h-4 w-4" /> Journal timeline + analytics</li>
                  <li className="flex items-center gap-2"><Check className="h-4 w-4" /> Basic RAG search</li>
                </ul>
                <div className="mt-6 pt-4 border-t">
                  <Button variant="outline" className="w-full" asChild>
                    <Link href="/signup">Get started</Link>
                  </Button>
                </div>
              </div>
              <div className="relative flex flex-col rounded-xl border-2 border-foreground/20 bg-background p-6">
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-foreground px-3 py-0.5 text-xs font-medium text-background">
                  Most popular
                </span>
                <p className="text-sm text-muted-foreground">Professional</p>
                <p className="mt-2 text-3xl font-bold">$99</p>
                <p className="text-xs text-muted-foreground">per clinician / month</p>
                <ul className="mt-4 space-y-2 text-sm">
                  <li className="flex items-center gap-2"><Check className="h-4 w-4" /> Unlimited patients</li>
                  <li className="flex items-center gap-2"><Check className="h-4 w-4" /> Full bias and trend reports</li>
                  <li className="flex items-center gap-2"><Check className="h-4 w-4" /> Conversation-aware RAG</li>
                  <li className="flex items-center gap-2"><Check className="h-4 w-4" /> BERTopic trend analysis</li>
                </ul>
                <div className="mt-6 pt-4 border-t">
                  <Button className="w-full" asChild>
                    <Link href="/signup">
                      Start free trial
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </Link>
                  </Button>
                </div>
              </div>
              <div className="flex flex-col rounded-xl border bg-background p-6">
                <p className="text-sm text-muted-foreground">Enterprise</p>
                <p className="mt-2 text-3xl font-bold">Custom</p>
                <p className="text-xs text-muted-foreground">multi-team deployment</p>
                <ul className="mt-4 space-y-2 text-sm">
                  <li className="flex items-center gap-2"><Check className="h-4 w-4" /> SSO and governance controls</li>
                  <li className="flex items-center gap-2"><Check className="h-4 w-4" /> Dedicated support</li>
                  <li className="flex items-center gap-2"><Check className="h-4 w-4" /> Custom compliance workflows</li>
                  <li className="flex items-center gap-2"><Check className="h-4 w-4" /> On-premise deployment option</li>
                </ul>
                <div className="mt-6 pt-4 border-t">
                  <Button variant="outline" className="w-full" asChild>
                    <Link href="/signup">Contact sales</Link>
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* faq */}
        <section className="border-t">
          <div className="mx-auto max-w-3xl px-6 py-20">
            <div className="mb-10 text-center">
              <h2 className="text-3xl font-bold tracking-tight">
                Frequently asked questions
              </h2>
              <p className="mt-2 text-sm text-muted-foreground">
                Everything you need to know before getting started
              </p>
            </div>
            <Accordion type="single" collapsible className="w-full">
              {faqs.map((faq, i) => (
                <AccordionItem key={i} value={`faq-${i}`}>
                  <AccordionTrigger>{faq.question}</AccordionTrigger>
                  <AccordionContent>
                    <p className="text-muted-foreground">{faq.answer}</p>
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          </div>
        </section>

        {/* final cta */}
        <section className="border-t bg-muted/20">
          <div className="mx-auto flex max-w-5xl flex-col items-center gap-6 px-6 py-20 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl border bg-muted">
              <Shield className="h-6 w-6" />
            </div>
            <h2 className="text-2xl font-semibold tracking-tight">
              Built for clinical workflows, not generic AI chat
            </h2>
            <p className="max-w-3xl text-sm leading-relaxed text-muted-foreground">
              CalmAI is designed to help you retrieve, organize, and review
              patient journal data with confidence. It never diagnoses, prescribes,
              or replaces clinical judgment. Every response includes source citations
              so your team can verify claims against the original patient entries.
            </p>
            <div className="flex gap-3">
              <Button asChild>
                <Link href="/signup">
                  Create your workspace
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
              <Button variant="outline" asChild>
                <Link href="/login">Sign in to existing workspace</Link>
              </Button>
            </div>
          </div>
        </section>
      </main>

      {/* footer */}
      <footer className="border-t">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6 text-sm text-muted-foreground">
          <span>&copy; {new Date().getFullYear()} CalmAI</span>
          <span>Built for therapists, by engineers who care.</span>
        </div>
      </footer>
    </div>
  );
}
