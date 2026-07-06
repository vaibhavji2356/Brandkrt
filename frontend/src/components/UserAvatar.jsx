import React, { useEffect, useState } from "react";

export default function UserAvatar({ src, initials, className = "", imageClassName = "", testId }) {
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setFailed(false);
  }, [src]);

  const baseClass = `overflow-hidden ${className}`;
  const fallback = initials || "U";

  return (
    <div className={baseClass} data-testid={testId}>
      {src && !failed ? (
        <img
          src={src}
          alt=""
          className={`h-full w-full object-cover ${imageClassName}`}
          onError={() => setFailed(true)}
        />
      ) : (
        fallback
      )}
    </div>
  );
}
