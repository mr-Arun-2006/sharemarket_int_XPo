import "./globals.css";

export const metadata = {
  title: "ShareM Int Xpo",
  description: "Share Market Intelligence System",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
