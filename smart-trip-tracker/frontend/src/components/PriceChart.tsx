import { dateTime, money, shortMoney, shortTime } from "../formatters";
import type { TripTracking } from "../types";

export function PriceChart({ tracking }: { tracking: TripTracking }) {
  const width = 720;
  const height = 280;
  const plot = { left: 68, right: 24, top: 34, bottom: 42 };
  const history = tracking.history.slice(-10);
  const prices = history.map((point) => point.total_price);
  const minimum = Math.min(...prices);
  const maximum = Math.max(...prices);
  const margin = Math.max((maximum - minimum) * 0.18, maximum * 0.035, 1);
  const floor = Math.max(0, minimum - margin);
  const ceiling = maximum + margin;
  const range = ceiling - floor;
  const x = (index: number) =>
    history.length === 1
      ? width / 2
      : plot.left +
        (index * (width - plot.left - plot.right)) / (history.length - 1);
  const y = (price: number) =>
    height -
    plot.bottom -
    ((price - floor) / range) * (height - plot.top - plot.bottom);
  const points = history
    .map((point, index) => `${x(index)},${y(point.total_price)}`)
    .join(" ");
  const areaPoints = `${plot.left},${height - plot.bottom} ${points} ${x(
    history.length - 1,
  )},${height - plot.bottom}`;
  const guides = [ceiling, (ceiling + floor) / 2, floor];
  const latest = history.at(-1)!;
  const latestIndex = history.length - 1;

  return (
    <>
      <svg
        className="price-chart"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="График изменения общей стоимости поездки"
      >
        <defs>
          <linearGradient id="price-area" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#ff5a5f" stopOpacity="0.2" />
            <stop offset="100%" stopColor="#ff5a5f" stopOpacity="0" />
          </linearGradient>
        </defs>
        {guides.map((price) => (
          <g key={price}>
            <line
              x1={plot.left}
              x2={width - plot.right}
              y1={y(price)}
              y2={y(price)}
            />
            <text className="axis-label" x={plot.left - 10} y={y(price) + 4}>
              {shortMoney(price)}
            </text>
          </g>
        ))}
        <polygon className="chart-area" points={areaPoints} />
        <polyline className="chart-line" points={points} />
        {history.map((point, index) => (
          <circle
            key={`${point.timestamp}-${index}`}
            cx={x(index)}
            cy={y(point.total_price)}
            r={index === latestIndex ? 6 : 4}
          >
            <title>
              {dateTime(point.timestamp)}: {money(point.total_price)}
            </title>
          </circle>
        ))}
        <text
          className="point-value"
          x={x(latestIndex)}
          y={Math.max(y(latest.total_price) - 15, 16)}
        >
          {money(latest.total_price)}
        </text>
        <text className="time-label" x={x(0)} y={height - 10}>
          {shortTime(history[0].timestamp)}
        </text>
        {history.length > 1 ? (
          <text
            className="time-label"
            textAnchor="end"
            x={x(latestIndex)}
            y={height - 10}
          >
            {shortTime(latest.timestamp)}
          </text>
        ) : null}
      </svg>

      <ol className="price-history" aria-label="История изменения цены">
        {[...history].reverse().map((point, reverseIndex) => {
          const index = history.length - 1 - reverseIndex;
          const previous = history[index - 1];
          const delta = previous ? point.total_price - previous.total_price : null;
          const direction =
            delta === null || delta === 0 ? "same" : delta > 0 ? "up" : "down";
          return (
            <li key={`history-${point.timestamp}-${index}`}>
              <time dateTime={point.timestamp}>{dateTime(point.timestamp)}</time>
              <strong>{money(point.total_price)}</strong>
              <span className={`price-delta ${direction}`}>
                {delta === null
                  ? "Первая цена"
                  : delta === 0
                    ? "Без изменений"
                    : `${delta > 0 ? "+" : ""}${money(delta)}`}
              </span>
            </li>
          );
        })}
      </ol>
    </>
  );
}
