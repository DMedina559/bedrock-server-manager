import React, { createContext, useContext, useEffect, useState } from "react";

const ThemeContext = createContext();

export const useTheme = () => useContext(ThemeContext);

export const ThemeProvider = ({ children }) => {
  // Default theme
  const [theme, setTheme] = useState(
    () => localStorage.getItem("theme") || "default",
  );

  useEffect(() => {
    let link = document.getElementById("theme-stylesheet");

    if (!link) {
      link = document.createElement("link");
      link.id = "theme-stylesheet";
      link.rel = "stylesheet";
      document.head.appendChild(link);
    }

    const standardThemes = [
      "default",
      "light",
      "gradient",
      "black",
      "red",
      "green",
      "blue",
      "yellow",
      "pink",
    ];

    let href;
    if (standardThemes.includes(theme)) {
      href = `/static/css/themes/${theme}.css`;
    } else {
      // Custom themes mounted at /themes
      href = `/themes/${theme}.css`;
    }

    link.href = href;
  }, [theme]);

  const changeTheme = (newTheme) => {
    setTheme(newTheme);
    localStorage.setItem("theme", newTheme);
  };

  return (
    <ThemeContext.Provider value={{ theme, changeTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};
