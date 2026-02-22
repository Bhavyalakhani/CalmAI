import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  Brain,
  Shield,
  BookOpen,
  ArrowRight,
  Sparkles,
} from "lucide-react";

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
    <div className="flex flex-col gap-3 rounded-xl border bg-background p-6">
      <div className="flex h-10 w-10 items-center justify-center rounded-lg border bg-muted">
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
        <section className="mx-auto flex max-w-4xl flex-col items-center gap-8 px-6 pb-24 pt-28 text-center">
          <div className="inline-flex items-center gap-2 rounded-full border px-4 py-1.5 text-sm text-muted-foreground">
            <Sparkles className="h-3.5 w-3.5" />
            Built for licensed therapists
          </div>

          <h1 className="text-5xl font-bold leading-[1.1] tracking-tight sm:text-6xl">
            Clinical intelligence
            <br />
            <span className="text-muted-foreground">without the noise</span>
          </h1>

          <p className="max-w-2xl text-lg text-muted-foreground">
            CalmAI helps mental health professionals organize, retrieve, and
            reason over patient journal data using RAG and semantic search. All
            clinical judgment stays with you.
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
        </section>

        {/* features */}
        <section className="border-t bg-muted/40">
          <div className="mx-auto grid max-w-6xl gap-8 px-6 py-24 sm:grid-cols-3">
            <FeatureCard
              icon={<BookOpen className="h-5 w-5" />}
              title="Patient Journaling"
              description="Patients write entries, receive analytical insights, and respond to therapist-assigned prompts, all in one secure space."
            />
            <FeatureCard
              icon={<Brain className="h-5 w-5" />}
              title="RAG-Powered Search"
              description="Ask natural language questions over patient data. Get contextual answers with source citations you can verify."
            />
            <FeatureCard
              icon={<Shield className="h-5 w-5" />}
              title="Clinician-First Design"
              description="No diagnoses, no treatment recommendations. CalmAI surfaces information - you make the clinical decisions."
            />
          </div>
        </section>

        {/* stats */}
        <section className="border-t">
          <div className="mx-auto grid max-w-4xl grid-cols-2 gap-8 px-6 py-20 sm:grid-cols-4">
            <StatBlock label="Conversations indexed" value="3,500+" />
            <StatBlock label="Journal entries" value="1,000+" />
            <StatBlock label="Embedding dimensions" value="384" />
            <StatBlock label="RAG faithfulness" value="90%+" />
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
