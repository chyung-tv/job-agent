"use client";

import { RunStatusBadge } from "./RunStatusBadge";
import { formatDistanceToNow } from "date-fns";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Hash, Clock, Calendar, CheckCircle2 } from "lucide-react";

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
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead>
            <div className="flex items-center gap-1.5">
              <Hash className="h-3.5 w-3.5 text-muted-foreground" />
              Run ID
            </div>
          </TableHead>
          <TableHead>
            <div className="flex items-center gap-1.5">
              <Clock className="h-3.5 w-3.5 text-muted-foreground" />
              Status
            </div>
          </TableHead>
          <TableHead>
            <div className="flex items-center gap-1.5">
              <CheckCircle2 className="h-3.5 w-3.5 text-muted-foreground" />
              Matches
            </div>
          </TableHead>
          <TableHead>
            <div className="flex items-center gap-1.5">
              <Calendar className="h-3.5 w-3.5 text-muted-foreground" />
              Created
            </div>
          </TableHead>
          <TableHead>Completed</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {runs.map((run) => (
          <TableRow key={run.id}>
            <TableCell>
              <code className="rounded bg-muted px-1.5 py-0.5 text-xs font-mono text-muted-foreground">
                {run.id.slice(0, 8)}...
              </code>
            </TableCell>
            <TableCell>
              <RunStatusBadge runId={run.id} initialStatus={run.status} />
            </TableCell>
            <TableCell>
              {run.total_matched_jobs > 0 ? (
                <span className="inline-flex items-center justify-center rounded-full bg-primary/10 px-2 py-0.5 text-sm font-semibold text-primary">
                  {run.total_matched_jobs}
                </span>
              ) : (
                <span className="text-muted-foreground">—</span>
              )}
            </TableCell>
            <TableCell className="text-muted-foreground">
              {formatDistanceToNow(new Date(run.created_at), {
                addSuffix: true,
              })}
            </TableCell>
            <TableCell className="text-muted-foreground">
              {run.completed_at
                ? formatDistanceToNow(new Date(run.completed_at), {
                    addSuffix: true,
                  })
                : "—"}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
