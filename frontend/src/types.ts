export type Summary = {
  n: number;
  maeMw: number | null;
  rmseMw: number | null;
  biasMw: number | null;
  mapePct: number | null;
  p50AbsErrorMw: number | null;
  p90AbsErrorMw: number | null;
  energyErrorGwh: number | null;
  forecastEnergyGwh: number | null;
  actualEnergyGwh: number | null;
  within500MwPct: number | null;
  within1000MwPct: number | null;
  overforecastHoursPct: number | null;
};

export type Overview = {
  meta: {
    builtAt: string;
    source: string;
    actualDataset: string;
    forecastDataset: string;
    deliveryFrom: string;
    deliveryTo: string;
    decisionRule: string;
    alignment: string;
    errorSign: string;
    actualPoints: number;
    forecastPoints: number;
    alignedHours: number;
  };
  summary: Summary;
  byHour: Array<Summary & { hourUk: number }>;
  byDay: Array<Summary & { deliveryDate: string }>;
  byWindLevel: Array<
    Summary & { level: string; actualFromMw: number; actualToMw: number }
  >;
  implications: string[];
};

export type Decision = {
  deliveryDate: string;
  decisionDate: string;
  decisionCutoffUk: string;
  publishTimeUsed: string | null;
  vintages: Array<{
    publishTime: string;
    pointCount: number;
    usableAtDaGate: boolean;
    hoursBeforeGate: number;
  }>;
  curve: Array<{
    startTime: string;
    hourUk: number;
    forecastMw: number;
    actualMw: number | null;
    errorMw: number | null;
    bandLowMw?: number;
    bandHighMw?: number;
  }>;
  daySummary: Summary;
  forecastEnergyGwh: number;
  actualEnergyGwh: number;
  uncertaintyBandMw: number;
  peakForecastMw: number | null;
  troughForecastMw: number | null;
};
