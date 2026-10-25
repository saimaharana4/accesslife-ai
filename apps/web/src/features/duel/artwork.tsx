"use client";

import { useEffect, useRef, useState } from "react";

type ArtworkProps = {
  src: string;
  title: string;
  missing?: boolean;
  className?: string;
};

export function Artwork(props: ArtworkProps) {
  // Changing the source or simulated availability starts a fresh image attempt.
  // A failed previous source must not leave a new, valid source in fallback mode.
  return (
    <ArtworkFrame
      key={`${props.missing ? "missing" : "image"}:${props.src}`}
      {...props}
    />
  );
}

function ArtworkFrame({
  src,
  missing = false,
  className = "choice-art",
}: ArtworkProps) {
  const [failed, setFailed] = useState(missing);
  const image = useRef<HTMLImageElement | null>(null);

  useEffect(() => {
    // An SSR image can fail before hydration attaches React's onError handler.
    // Reconcile that already-completed failure once the element is available.
    if (
      !missing &&
      image.current?.complete &&
      image.current.naturalWidth === 0
    ) {
      setFailed(true);
    }
  }, [missing]);

  return (
    <div className={`${className}${failed ? " artwork-fallback" : ""}`}>
      {failed ? (
        <div className="fallback-composition">
          <span className="fallback-star" aria-hidden="true">
            ✳
          </span>
          <span className="mono-label">ORIGINAL TITLE CARD</span>
          <span className="fallback-note">Artwork unavailable.</span>
        </div>
      ) : (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          ref={image}
          src={src}
          alt=""
          width="600"
          height="800"
          onError={() => setFailed(true)}
        />
      )}
    </div>
  );
}
