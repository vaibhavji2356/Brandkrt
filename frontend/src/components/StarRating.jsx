import React from "react";
import { Star } from "lucide-react";

export default function StarRating({ value = 0, max = 5, size = 16, onChange, readOnly = true, testId }) {
  const [hover, setHover] = React.useState(0);
  const active = hover || value;
  const stars = Array.from({ length: max }, (_, i) => i + 1);
  return (
    <div className="inline-flex items-center gap-0.5" data-testid={testId}>
      {stars.map((i) => {
        const filled = i <= active;
        const half = !filled && i - 0.5 <= active;
        const cls = filled
          ? "text-secondary fill-secondary"
          : half
          ? "text-secondary"
          : "text-muted-foreground/40";
        return (
          <button
            key={i}
            type="button"
            disabled={readOnly}
            onClick={() => !readOnly && onChange?.(i)}
            onMouseEnter={() => !readOnly && setHover(i)}
            onMouseLeave={() => !readOnly && setHover(0)}
            className={`${readOnly ? "cursor-default" : "cursor-pointer"} bg-transparent border-0 p-0 m-0 inline-flex`}
            data-testid={testId ? `${testId}-star-${i}` : undefined}
            aria-label={`${i} star`}
          >
            <Star style={{ width: size, height: size }} className={cls} />
          </button>
        );
      })}
    </div>
  );
}
