"use client";

import { RunStatusBadge } from "./RunStatusBadge";
import { formatDistanceToNow } from "date-fns";

interface Run {
  id: string;
  status: string;
  task_id: string | null;
  error_message: string | null;
  total_matched_jobs: number;
  completed_at: Date | null;
  created_at: Date;
  updated_at: Date;
}

interface RunsTableProps {
  runs: Run[];
}

export function RunsTable({ runs }: RunsTableProps) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b text-left text-sm text-muted-foreground">
            <th className="pb-3 pr-4 font-medium">Run ID</th>
            <th className="pb-3 pr-4 font-medium">Status</th>
            <th className="pb-3 pr-4 font-medium">Matches</th>
            <th className="pb-3 pr-4 font-medium">Created</th>
            <th className="pb-3 font-medium">Completed</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr key={run.id} className="border-b last:border-0">
              <td className="py-3 pr-4">
                <code className="text-xs text-muted-foreground">
                  {run.id.slice(0, 8)}...
                </code>
              </td>
              <td className="py-3 pr-4">
                <RunStatusBadge runId={run.id} initialStatus={run.status} />
              </td>
              <td className="py-3 pr-4 text-sm">
                {run.total_matched_jobs > 0 ? (
                  <span className="font-medium">{run.total_matched_jobs}</span>
                ) : (
                  <span className="text-muted-foreground">-</span>
                )}
              </td>
              <td className="py-3 pr-4 text-sm text-muted-foreground">
                {formatDistanceToNow(new Date(run.created_at), {
                  addSuffix: true,
                })}
              </td>
              <td className="py-3 text-sm text-muted-foreground">
                {run.completed_at
                  ? formatDistanceToNow(new Date(run.completed_at), {
                      addSuffix: true,
                    })
                  : "-"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
