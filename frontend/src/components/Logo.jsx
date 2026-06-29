import React from "react";
import { LOGO, BRAND } from "@/lib/brand";

export default function Logo({ variant = "full", className = "", iconClassName = "", textClassName = "" }) {
  if (variant === "icon") {
    return (
      <img
        src={LOGO.icon}
        alt={`${BRAND.name} icon`}
        className={`h-9 w-9 rounded-md object-cover ${iconClassName} ${className}`}
        data-testid="brand-logo-icon"
      />
    );
  }
  return (
    <div className={`flex items-center gap-2.5 ${className}`} data-testid="brand-logo-full">
      <img src={LOGO.icon} alt={`${BRAND.name} mark`} className={`h-9 w-9 rounded-md ${iconClassName}`} />
      <span className={`font-display text-xl tracking-tight text-primary dark:text-white ${textClassName}`}>
        Brand<span className="gold-text font-semibold">krt</span>
      </span>
    </div>
  );
}
