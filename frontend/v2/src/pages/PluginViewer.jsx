import React, { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

const PluginViewer = () => {
    const [searchParams] = useSearchParams();
    const url = searchParams.get("url");
    const [isLoading, setIsLoading] = useState(true);

    // Reset loading state when URL changes
    useEffect(() => {
        setIsLoading(true);
    }, [url]);

    if (!url) {
        return (
            <div className="container">
                <div className="message-box message-error">
                    No plugin URL provided.
                </div>
            </div>
        );
    }

    return (
        <div style={{ height: "calc(100vh - 100px)", display: "flex", flexDirection: "column" }}>
            <div className="header">
                <h1>Plugin View</h1>
            </div>

            <div style={{ flexGrow: 1, position: "relative", background: "#fff", borderRadius: "8px", overflow: "hidden" }}>
                {isLoading && (
                    <div style={{
                        position: "absolute", top: 0, left: 0, right: 0, bottom: 0,
                        display: "flex", alignItems: "center", justifyContent: "center",
                        background: "rgba(0,0,0,0.1)", zIndex: 1
                    }}>
                        Loading Plugin Content...
                    </div>
                )}
                <iframe
                    src={url}
                    title="Plugin Content"
                    style={{ width: "100%", height: "100%", border: "none" }}
                    onLoad={() => setIsLoading(false)}
                />
            </div>
        </div>
    );
};

export default PluginViewer;
