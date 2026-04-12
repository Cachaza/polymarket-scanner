"use client";

import { useRouter } from "next/navigation";
import { startTransition, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { runSystemAction, type JobActionResponse } from "@/lib/api";

function parseHours(value: string) {
  return value
    .split(",")
    .map((item) => Number(item.trim()))
    .filter((item) => Number.isFinite(item) && item >= 0);
}

function ActionButton({
  disabled,
  label,
  onClick,
}: {
  disabled: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="rounded-xl border border-line bg-white px-4 py-3 text-sm font-medium text-slate-900 transition hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-50"
    >
      {label}
    </button>
  );
}

export function SystemActionsPanel() {
  const router = useRouter();
  const [runningAction, setRunningAction] = useState<string | null>(null);
  const [errorText, setErrorText] = useState<string | null>(null);
  const [result, setResult] = useState<JobActionResponse | null>(null);
  const [backtestHours, setBacktestHours] = useState("6,24,72");
  const [latentHours, setLatentHours] = useState("24,72,120");
  const [confirmHours, setConfirmHours] = useState("24");
  const [maxDrift, setMaxDrift] = useState("0.05");
  const [minNotional, setMinNotional] = useState("1000");
  const [minWalletScore, setMinWalletScore] = useState("60");

  const submitAction = async (action: string, body?: Record<string, unknown>) => {
    setRunningAction(action);
    setErrorText(null);
    try {
      const response = await runSystemAction({ action, ...body });
      setResult(response);
      startTransition(() => {
        router.refresh();
      });
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "Action failed");
    } finally {
      setRunningAction(null);
    }
  };

  const disabled = runningAction !== null;

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Run Jobs</CardTitle>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            Trigger the safer scanner jobs directly from the UI and rerun the research exports with custom latent-entry filters.
          </p>
        </div>
        {runningAction ? <Badge className="border-warn/30 bg-warn/10 text-warn">running {runningAction}</Badge> : null}
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          <ActionButton disabled={disabled} label="Discover" onClick={() => void submitAction("discover")} />
          <ActionButton disabled={disabled} label="Refresh Leaderboard" onClick={() => void submitAction("refresh-leaderboard")} />
          <ActionButton disabled={disabled} label="Snapshot" onClick={() => void submitAction("snapshot")} />
          <ActionButton disabled={disabled} label="Score Alerts" onClick={() => void submitAction("score-alerts")} />
          <ActionButton
            disabled={disabled}
            label="Backtest Alerts"
            onClick={() => void submitAction("backtest", { hours: parseHours(backtestHours) })}
          />
          <ActionButton disabled={disabled} label="Run Full Cycle" onClick={() => void submitAction("run-cycle")} />
        </div>

        <div className="rounded-2xl border border-line bg-slate-50/80 p-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <div className="text-xs uppercase tracking-[0.16em] text-muted">Latent Entry Filters</div>
              <p className="mt-1 text-sm text-slate-600">Tune the delayed-entry hypothesis and rerun the latent research export.</p>
            </div>
            <ActionButton
              disabled={disabled}
              label="Run Latent Backtest"
              onClick={() =>
                void submitAction("latent-backtest", {
                  hours: parseHours(latentHours),
                  confirm_hours: Number(confirmHours),
                  max_drift: Number(maxDrift),
                  min_notional: Number(minNotional),
                  min_wallet_score: Number(minWalletScore),
                })
              }
            />
          </div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
            <label className="space-y-2 text-sm text-slate-700">
              <span>Alert backtest hours</span>
              <Input value={backtestHours} onChange={(event) => setBacktestHours(event.target.value)} placeholder="6,24,72" />
            </label>
            <label className="space-y-2 text-sm text-slate-700">
              <span>Latent horizons</span>
              <Input value={latentHours} onChange={(event) => setLatentHours(event.target.value)} placeholder="24,72,120" />
            </label>
            <label className="space-y-2 text-sm text-slate-700">
              <span>Confirm hours</span>
              <Input value={confirmHours} onChange={(event) => setConfirmHours(event.target.value)} inputMode="numeric" />
            </label>
            <label className="space-y-2 text-sm text-slate-700">
              <span>Max flat drift</span>
              <Input value={maxDrift} onChange={(event) => setMaxDrift(event.target.value)} inputMode="decimal" />
            </label>
            <label className="space-y-2 text-sm text-slate-700">
              <span>Min notional / wallet score</span>
              <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-1">
                <Input value={minNotional} onChange={(event) => setMinNotional(event.target.value)} inputMode="decimal" />
                <Input value={minWalletScore} onChange={(event) => setMinWalletScore(event.target.value)} inputMode="decimal" />
              </div>
            </label>
          </div>
        </div>

        {errorText ? (
          <div className="rounded-2xl border border-bad/30 bg-bad/10 px-4 py-3 text-sm text-bad">{errorText}</div>
        ) : null}
        {result ? (
          <div className="rounded-2xl border border-line px-4 py-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="font-medium">{result.job_name}</div>
                <div className="text-sm text-slate-600">
                  rows {result.rows_written ?? "n/a"}{result.output_path ? ` • ${result.output_path}` : ""}
                </div>
              </div>
              <Badge className="border-good/30 bg-good/10 text-good">{result.status}</Badge>
            </div>
            <pre className="mt-3 overflow-x-auto rounded-xl bg-slate-50 p-3 font-mono text-xs text-slate-700">
              {JSON.stringify(result.meta, null, 2)}
            </pre>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
