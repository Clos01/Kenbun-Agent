import type { Metadata } from "next";
import { Plus_Jakarta_Sans, Cormorant_Garamond, Space_Mono } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/context/ThemeContext";
import { TenantProvider } from "@/context/TenantContext";
import Script from "next/script";

const plusJakarta = Plus_Jakarta_Sans({
  variable: "--font-plus-jakarta",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700", "800"],
});

const cormorant = Cormorant_Garamond({
  variable: "--font-cormorant",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  style: ["normal", "italic"],
});

const spaceMono = Space_Mono({
  variable: "--font-space-mono",
  subsets: ["latin"],
  weight: ["400", "700"],
});

export const metadata: Metadata = {
  title: "Kenbun — Build Console",
  description: "Real-time visibility into agent workflows and software delivery.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${plusJakarta.variable} ${cormorant.variable} ${spaceMono.variable} h-full antialiased`}
    >
      <head>
        <Script
          id="theme-script"
          strategy="beforeInteractive"
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var saved = localStorage.getItem('ag_theme_v2');
                  var systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
                  var theme = saved || (systemPrefersDark ? 'dark' : 'light');
                  
                  if (theme === 'light') {
                    document.documentElement.classList.add('light');
                  } else {
                    document.documentElement.classList.remove('light');
                  }
                } catch (e) {
                  try {
                    var fallbackTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
                    if (fallbackTheme === 'light') {
                      document.documentElement.classList.add('light');
                    } else {
                      document.documentElement.classList.remove('light');
                    }
                  } catch (err) {}
                }
              })();
            `
          }}
        />
      </head>
      <body suppressHydrationWarning className="min-h-full font-sans">
        <ThemeProvider>
          <TenantProvider>
            {children}
          </TenantProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}

