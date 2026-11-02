"use client";

import { ApiError, Fact, Loading, Panel } from "@/components/lab/ui";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { labApi } from "@/lib/lab-api";
import { formatMb } from "@/lib/format";
import { useApi } from "@/lib/use-api";

const LOW_DISK_MB = 15 * 1024;

export function HardwarePanel() {
  const { data: hw, error, loading, reload } = useApi(labApi.hardware);
  if (loading) return <Loading what="hardware" />;
  if (error || !hw) return <ApiError error={error ?? "No data"} onRetry={reload} />;
  const lowDisk = hw.disk_free_mb < LOW_DISK_MB;
  return (
    <Panel title="This machine">
      <dl className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Fact label="Chip" value={hw.chip ?? `${hw.arch} (${hw.os})`} />
        <Fact label="Memory" value={`${formatMb(hw.ram_total_mb)} total`} />
        <Fact label="Available now" value={formatMb(hw.ram_available_mb)} warn={hw.ram_available_mb < 4096} />
        <Fact label="Swap in use" value={formatMb(hw.swap_used_mb)} warn={hw.swap_used_mb > 2048} />
        <Fact label="Disk free" value={formatMb(hw.disk_free_mb)} warn={lowDisk} />
        <Fact label="Metal" value={hw.metal ?? "not detected"} />
        <Fact
          label="Power"
          value={hw.on_battery === null ? "unknown" : hw.on_battery ? "On battery" : "Plugged in"}
          warn={hw.on_battery === true}
        />
        <Fact
          label="Cores"
          value={`${hw.cpu_cores_total ?? "?"}${hw.cpu_cores_performance ? ` (${hw.cpu_cores_performance} performance)` : ""}`}
        />
      </dl>
      {lowDisk && (
        <Alert variant="warning" className="mt-4">
          <AlertTitle>Low free disk space</AlertTitle>
          <AlertDescription>
            Local models are large. Simulacra never downloads models for you; check free space
            before pulling one.
          </AlertDescription>
        </Alert>
      )}
      {hw.low_power_mode && (
        <Alert variant="warning" className="mt-4">
          <AlertTitle>Low Power Mode is on</AlertTitle>
          <AlertDescription>Benchmarks and runs will be slower and less representative.</AlertDescription>
        </Alert>
      )}
      <p className="mt-4 text-xs text-muted-foreground">
        Hardware details stay on this machine and are never sent anywhere. The Mac stops running
        inference if it goes to sleep; keep it awake for long runs.
      </p>
    </Panel>
  );
}
