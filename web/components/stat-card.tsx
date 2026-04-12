import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function StatCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: string | number;
  hint?: string;
}) {
  return (
    <Card>
      <CardHeader className="border-b-0 pb-0">
        <CardTitle>{label}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="font-mono text-3xl font-semibold tracking-tight text-slate-950">{value}</div>
        {hint ? <p className="mt-2 text-sm text-slate-600">{hint}</p> : null}
      </CardContent>
    </Card>
  );
}
