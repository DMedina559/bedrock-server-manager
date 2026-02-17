import React, { useState, useEffect, useRef } from "react";
import "../styles/SidebarEnhanced.css";

const SidebarLabel = ({ children }) => {
  const textRef = useRef(null);
  const containerRef = useRef(null);
  const [isOverflowing, setIsOverflowing] = useState(false);
  const [scrollDistance, setScrollDistance] = useState(0);

  useEffect(() => {
    const checkOverflow = () => {
      if (textRef.current && containerRef.current) {
        const textWidth = textRef.current.scrollWidth;
        const containerWidth = containerRef.current.clientWidth;

        // If text is wider than container, it overflows
        if (textWidth > containerWidth) {
          setIsOverflowing(true);
          // Add a buffer or use exact width
          setScrollDistance(textWidth - containerWidth);
        } else {
          setIsOverflowing(false);
          setScrollDistance(0);
        }
      }
    };

    // Check initially
    checkOverflow();

    // Check on resize (window resize might change sidebar width slightly or responsiveness)
    window.addEventListener("resize", checkOverflow);
    return () => window.removeEventListener("resize", checkOverflow);
  }, [children]);

  return (
    <span
      className={`nav-label-wrapper ${isOverflowing ? "overflowing" : ""}`}
      ref={containerRef}
      title={children}
      style={
        isOverflowing ? { "--scroll-distance": `-${scrollDistance}px` } : {}
      }
    >
      <span className="nav-label-text" ref={textRef}>
        {children}
      </span>
    </span>
  );
};

export default SidebarLabel;
