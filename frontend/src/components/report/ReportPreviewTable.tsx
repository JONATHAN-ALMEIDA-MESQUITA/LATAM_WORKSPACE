import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import type { ReportPreviewResult } from "@/types";

export function ReportPreviewTable({
  preview,
  generatedSql,
}: {
  preview: ReportPreviewResult | null;
  generatedSql?: string | null;
}) {
  return (
    <Card
      title="Preview"
      actions={
        preview ? (
          <Badge tone={preview.truncated ? "warning" : "success"}>
            {preview.row_count} linha(s)
            {preview.truncated ? " (truncado)" : ""}
          </Badge>
        ) : null
      }
    >
      {!preview ? (
        <EmptyState
          title="Sem resultados"
          description="Configure o relatório e clique em Executar preview."
        />
      ) : (
        <>
          {(preview.notes || generatedSql || preview.generated_sql) && (
            <div className="mb-3 space-y-2">
              {preview.notes && (
                <p className="text-xs text-amber-700">{preview.notes}</p>
              )}
              {(generatedSql || preview.generated_sql) && (
                <details className="rounded border border-slate-200 bg-slate-50 p-2 text-xs">
                  <summary className="cursor-pointer font-medium text-slate-700">
                    SQL gerado
                  </summary>
                  <pre className="mt-2 overflow-x-auto whitespace-pre-wrap font-mono text-slate-600">
                    {generatedSql || preview.generated_sql}
                  </pre>
                </details>
              )}
            </div>
          )}
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50">
                  {preview.columns.map((col) => (
                    <th key={col} className="whitespace-nowrap px-3 py-2 font-semibold">
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((row, i) => (
                  <tr key={i} className="border-b border-slate-100">
                    {preview.columns.map((col) => (
                      <td key={col} className="whitespace-nowrap px-3 py-1.5 font-mono">
                        {row[col] == null ? "—" : String(row[col])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Card>
  );
}
