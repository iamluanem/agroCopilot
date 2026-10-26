import { TaskExecution } from "@/components/ops/task-execution";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <TaskExecution taskId={Number(id)} />;
}
