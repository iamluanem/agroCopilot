import { CopilotChat } from "@/components/copilot/chat";
import { DemoBadge } from "@/components/ui/demo-badge";
import { PageHeader } from "@/components/ui/page";

export default function CopilotPage() {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <PageHeader title="Copilot" subtitle="Ask in plain language. Every answer cites the records it used." right={<DemoBadge />} />
      <div className="min-h-0 flex-1 bg-slate-50"><CopilotChat source="copilot" /></div>
    </div>
  );
}
