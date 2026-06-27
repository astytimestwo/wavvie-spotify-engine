import { useEffect, useState } from "react";
import { extractDominantColor } from "../../lib/colors";

export function ArtworkBlur({ artworkUrl, children, className = "" }) {
  const [color, setColor] = useState("#7C3AED");

  useEffect(() => {
    let active = true;
    extractDominantColor(artworkUrl).then((nextColor) => {
      if (active) setColor(nextColor);
    });
    return () => {
      active = false;
    };
  }, [artworkUrl]);

  return (
    <div
      className={className}
      style={{
        boxShadow: `inset 0 0 80px 40px ${color}33`,
        transition: "box-shadow 600ms ease",
      }}
    >
      {children}
    </div>
  );
}
