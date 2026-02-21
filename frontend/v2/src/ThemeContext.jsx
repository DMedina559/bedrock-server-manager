import React, { createContext, useContext, useEffect } from "react";
import { useAuth } from "./AuthContext";
import { request } from "./api";

const ThemeContext = createContext();

export const useTheme = () => useContext(ThemeContext);

export const ThemeProvider = ({ children }) => {
  const { user, checkUser } = useAuth();

  // Use user's theme or default. Do not use local storage.
  const theme = user?.theme || "default";

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

  const changeTheme = async (newTheme) => {
    try {
      await request("/api/account/theme", {
        method: "POST",
        body: { theme: newTheme },
      });
      // Refresh user data to get the new theme applied
      await checkUser();
    } catch (error) {
      console.error("Failed to update theme:", error);
    }
  };

  return (
    <ThemeContext.Provider value={{ theme, changeTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};
