"use client";

import { useEffect, useRef } from "react";
import * as echarts from "echarts";

export function EChartWrapper({
  option,
  height = 280,
}: {
  option: echarts.EChartsCoreOption;
  height?: number;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const chart = echarts.init(el, "dark", { renderer: "canvas" });
    chartRef.current = chart;

    const observer = new ResizeObserver(() => {
      chart.resize();
    });
    observer.observe(el);

    return () => {
      observer.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (chartRef.current) {
      chartRef.current.setOption(
        {
          backgroundColor: "transparent",
          ...option,
        },
        true
      );
    }
  }, [option]);

  return <div ref={containerRef} style={{ width: "100%", height }} />;
}
