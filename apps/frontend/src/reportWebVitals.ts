const reportWebVitals = (onPerfEntry?: (metric: any) => void) => {
    if (onPerfEntry && onPerfEntry instanceof Function) {
        import("web-vitals").then((webVitals) => {
            // Use the newer web-vitals API
            const { onCLS, onFCP, onLCP, onTTFB, onINP } = webVitals;

            // Only use metrics that exist in the API
            if (onCLS) onCLS(onPerfEntry);
            if (onFCP) onFCP(onPerfEntry);
            if (onLCP) onLCP(onPerfEntry);
            if (onTTFB) onTTFB(onPerfEntry);
            if (onINP) onINP(onPerfEntry);
        });
    }
};

export default reportWebVitals;
