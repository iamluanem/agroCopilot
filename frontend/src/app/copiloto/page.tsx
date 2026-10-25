import { CopilotChat } from "@/components/copilot/chat";
import { DemoBadge } from "@/components/ui/demo-badge";
import { PageHeader } from "@/components/ui/page";

export default function CopilotoPage() {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <PageHeader title="Copiloto" subtitle="Pergunte em linguagem natural. As respostas citam os registros usados." right={<DemoBadge />} />
      <div className="min-h-0 flex-1 bg-slate-50"><CopilotChat source="copiloto" /></div>
    </div>
  );
}
