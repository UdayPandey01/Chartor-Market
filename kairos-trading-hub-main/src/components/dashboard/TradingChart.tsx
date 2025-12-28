import { CandlestickSeries, ColorType, IChartApi, UTCTimestamp, createChart } from 'lightweight-charts';
import React, { useEffect, useRef } from 'react';

export const TradingChart = ({ data }) => {
    const chartContainerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<IChartApi | null>(null);

    useEffect(() => {
        if (!chartContainerRef.current) return;

        // 1. Configure the Chart Look (Dark Mode)
        const chart = createChart(chartContainerRef.current, {
            layout: {
                background: { type: ColorType.Solid, color: '#09090b' }, // Match your UI background
                textColor: '#d4d4d8', // Zinc-300
            },
            grid: {
                vertLines: { color: '#1f1f22' }, // Subtle grid
                horzLines: { color: '#1f1f22' },
            },
            width: chartContainerRef.current.clientWidth,
            height: 500,
            timeScale: {
                timeVisible: true,
                secondsVisible: false,
                borderColor: '#27272a',
            },
            rightPriceScale: {
                borderColor: '#27272a',
            },
        });

        // 2. Add Candlestick Series (Green/Red)
        // lightweight-charts v5+ uses addSeries() instead of addCandlestickSeries().
        const candlestickSeries = chart.addSeries(CandlestickSeries, {
            upColor: '#10b981',        // Emerald Green (Win)
            downColor: '#ef4444',      // Red (Loss)
            borderVisible: false,
            wickUpColor: '#10b981',
            wickDownColor: '#ef4444',
        });

        // 3. Inject Data
        if (data && data.length > 0) {
            candlestickSeries.setData(
                data.map((c) => ({
                    ...c,
                    time: c.time as UTCTimestamp,
                }))
            );
        }

        chart.timeScale().fitContent();
        chartRef.current = chart;

        // Resize Handler
        const handleResize = () => {
            chart.applyOptions({ width: chartContainerRef.current?.clientWidth });
        };
        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
            chart.remove();
        };
    }, [data]);

    return (
        <div ref={chartContainerRef} className="w-full h-[500px]" />
    );
};