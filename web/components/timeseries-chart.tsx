"use client";

import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type Point = {
  snapshot_ts: string;
  yes_price: number | null;
  yes_top5_seen_share: number | null;
};

export function TimeSeriesChart({ data }: { data: Point[] }) {
  return (
    <div className="h-72 w-full">
      <ResponsiveContainer>
        <LineChart data={data}>
          <XAxis dataKey="snapshot_ts" tick={{ fontSize: 11 }} tickMargin={10} minTickGap={24} />
          <YAxis yAxisId="price" tick={{ fontSize: 11 }} domain={[0, 1]} />
          <YAxis yAxisId="share" orientation="right" tick={{ fontSize: 11 }} domain={[0, 1]} />
          <Tooltip />
          <Line yAxisId="price" dataKey="yes_price" stroke="hsl(205 68% 42%)" dot={false} strokeWidth={2.5} />
          <Line yAxisId="share" dataKey="yes_top5_seen_share" stroke="hsl(28 92% 48%)" dot={false} strokeWidth={2.2} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
