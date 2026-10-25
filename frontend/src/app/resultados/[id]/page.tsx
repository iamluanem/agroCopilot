import { OutcomeReport } from "@/components/ops/outcome-report";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <OutcomeReport outcomeId={Number(id)} />;
}
