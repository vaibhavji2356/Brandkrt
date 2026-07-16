import React, { useEffect, useState } from "react";
import { assetUrl } from "@/lib/brand";

export default function UserAvatar({ src, initials, className = "", imageClassName = "", testId }) {
  const [failed, setFailed] = useState(false);
  const resolvedSrc = assetUrl(src);

  useEffect(() => {
    setFailed(false);
  }, [resolvedSrc]);

  const baseClass = `overflow-hidden bg-primary text-primary-foreground ${className}`;
  const fallback = (initials || "U").slice(0, 2).toUpperCase();

  return (
    <div className={baseClass} data-testid={testId}>
      {resolvedSrc && !failed ? (
        <img
          src={resolvedSrc}
          alt=""
          className={`h-full w-full object-cover ${imageClassName}`}
          onError={() => setFailed(true)}
        />
      ) : (
        <span className="flex h-full w-full items-center justify-center text-sm font-semibold">
          {fallback}
        </span>
      )}
    </div>
  );
}
