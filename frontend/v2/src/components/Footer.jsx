import React, { useEffect, useState } from "react";
import { get } from "../api";
import "./Footer.css";

const Footer = () => {
  const [appVersion, setAppVersion] = useState("Unknown");

  useEffect(() => {
    const fetchInfo = async () => {
      try {
        const data = await get("/api/info");
        if (data && data.status === "success" && data.info) {
          setAppVersion(data.info.app_version);
        }
      } catch (error) {
        console.error("Failed to fetch app info for footer:", error);
      }
    };

    fetchInfo();
  }, []);

  return (
    <footer className="footer">
      <p>
        <a
          href="https://bedrock-server-manager.readthedocs.io/en/latest/"
          target="_blank"
          rel="noopener noreferrer"
        >
          Docs
        </a>{" "}
        |{" "}
        <a href="/docs" target="_blank" rel="noopener noreferrer">
          HTTP API
        </a>{" "}
        |{" "}
        <a
          href="https://github.com/dmedina559"
          target="_blank"
          rel="noopener noreferrer"
        >
          GitHub
        </a>
        <br />
        {appVersion} © MIT 2025-2026
      </p>
      <a href="/legacy/">Old UI</a>
    </footer>
  );
};

export default Footer;
