import { FieldPage } from "@/components/intel/field-page";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <FieldPage fieldId={Number(id)} />;
}
