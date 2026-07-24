import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { ToastProvider } from "@/components/ToastProvider";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Ushuru Lens | Powered by Techbiz Group",
  description: "Ushuru Lens - KRA Reconciliation & Tax Compliance Engine powered by Techbiz",
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
      className={`${inter.variable} ${jetbrainsMono.variable} h-full antialiased`}
    >
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                function removeBisSkin() {
                  document.querySelectorAll('[bis_skin_checked]').forEach(function(el) {
                    el.removeAttribute('bis_skin_checked');
                  });
                }
                removeBisSkin();
                if (typeof MutationObserver !== 'undefined') {
                  new MutationObserver(function(mutations) {
                    for (var i = 0; i < mutations.length; i++) {
                      var mutation = mutations[i];
                      if (mutation.type === 'attributes' && mutation.attributeName === 'bis_skin_checked') {
                        mutation.target.removeAttribute('bis_skin_checked');
                      } else if (mutation.addedNodes.length) {
                        removeBisSkin();
                      }
                    }
                  }).observe(document.documentElement, {
                    attributes: true,
                    subtree: true,
                    attributeFilter: ['bis_skin_checked']
                  });
                }
              })();
            `,
          }}
        />
      </head>
      <body suppressHydrationWarning className="min-h-full flex flex-col">
        <ToastProvider>{children}</ToastProvider>
      </body>
    </html>
  );
}
