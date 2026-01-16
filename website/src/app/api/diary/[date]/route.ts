/**
 * API Route: /api/diary/[date]
 * Returns a fully structured diary entry for the requested date
 * Uses mocked data - in production, would query database or LangGraph backend
 */

import { NextRequest, NextResponse } from "next/server";
import { DiaryEntry } from "@/types";

/**
 * Generate mocked diary entry for a given date
 * This simulates what would come from a database or AI generation pipeline
 */
function generateMockedDiaryEntry(date: string): DiaryEntry {
  const dateObj = new Date(date);
  const formattedDate = dateObj.toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  return {
    metadata: {
      date,
      title: `World Digest — ${formattedDate}`,
      summary:
        "A comprehensive snapshot of global events across politics, finance, entertainment, and markets.",
      generatedAt: new Date().toISOString(),
    },
    sections: [
      {
        id: "political-news",
        title: "Political News",
        order: 1,
        content: `
          <h3>Global Political Developments</h3>
          <p>
            <strong>United States:</strong> The Senate passed a bipartisan infrastructure bill with 68 votes,
            marking a rare moment of cross-party cooperation. The legislation allocates $1.2 trillion toward
            roads, bridges, and broadband expansion over the next decade.
          </p>
          <p>
            <strong>European Union:</strong> The European Commission announced new climate targets, committing
            to reduce carbon emissions by 55% by 2030. Several member states expressed concerns about the
            economic impact on manufacturing sectors.
          </p>
          <p>
            <strong>Asia-Pacific:</strong> Diplomatic tensions continued in the South China Sea as multiple
            nations reaffirmed territorial claims. The ASEAN summit concluded with a joint statement calling
            for peaceful resolution through international law.
          </p>
        `,
        sources: [
          {
            title: "U.S. Senate — Legislation & Records",
            url: "https://www.senate.gov/legislative/legislative_home.htm",
          },
          {
            title: "European Commission — Climate Action",
            url: "https://climate.ec.europa.eu/",
          },
          {
            title: "ASEAN — Official Statements",
            url: "https://asean.org/",
          },
        ],
      },
      {
        id: "financial-news",
        title: "Financial News",
        order: 2,
        content: `
          <h3>Markets and Economic Indicators</h3>
          <p>
            Global markets showed mixed performance as investors processed new inflation data. The Federal
            Reserve signaled potential interest rate adjustments in the coming quarter, leading to volatility
            in bond markets.
          </p>
          <ul>
            <li><strong>S&P 500:</strong> Closed up 0.7% at 4,521</li>
            <li><strong>NASDAQ:</strong> Gained 1.2% driven by tech sector strength</li>
            <li><strong>Gold:</strong> Rose $15 to $1,842/oz amid economic uncertainty</li>
            <li><strong>Crude Oil:</strong> WTI settled at $74.21/barrel</li>
          </ul>
          <p>
            <strong>Cryptocurrency:</strong> Bitcoin traded sideways around $43,000 while Ethereum saw
            increased activity following successful network upgrades.
          </p>
        `,
        sources: [
          {
            title: "U.S. Federal Reserve — Press Releases",
            url: "https://www.federalreserve.gov/newsevents/pressreleases.htm",
          },
          {
            title: "U.S. Bureau of Labor Statistics — Inflation & CPI",
            url: "https://www.bls.gov/cpi/",
          },
          {
            title: "U.S. Energy Information Administration — Petroleum",
            url: "https://www.eia.gov/petroleum/",
          },
        ],
      },
      {
        id: "entertainment-news",
        title: "Entertainment News",
        order: 3,
        content: `
          <h3>Film, Television, and Cultural Events</h3>
          <p>
            The Venice Film Festival announced its lineup for the upcoming season, featuring several
            highly anticipated premieres from acclaimed directors. Industry analysts predict a strong
            showing for international cinema this year.
          </p>
          <p>
            <strong>Streaming Wars:</strong> Netflix announced a new tier structure while Disney+ reported
            subscriber growth in emerging markets. The competition for original content continues to intensify
            with record-breaking production budgets.
          </p>
          <p>
            <strong>Gaming:</strong> Major publishers revealed holiday season releases, with particular
            focus on next-generation console exclusives and cross-platform multiplayer experiences.
          </p>
        `,
        sources: [
          {
            title: "La Biennale di Venezia — Venice Film Festival",
            url: "https://www.labiennale.org/en/cinema",
          },
          {
            title: "Netflix — Newsroom",
            url: "https://about.netflix.com/en/newsroom",
          },
          {
            title: "The Walt Disney Company — Press Releases",
            url: "https://thewaltdisneycompany.com/news/",
          },
        ],
      },
      {
        id: "music-releases",
        title: "Music Releases",
        order: 4,
        content: `
          <h3>New Releases and Industry Trends</h3>
          <p>
            Several major artists dropped surprise releases this week, continuing the trend of
            direct-to-fan distribution strategies that bypass traditional marketing cycles.
          </p>
          <ul>
            <li><strong>Pop:</strong> Chart-topping singles from established artists dominated streaming platforms</li>
            <li><strong>Hip-Hop:</strong> Collaborative projects between cross-generational artists gained traction</li>
            <li><strong>Electronic:</strong> Festival season announcements revealed experimental lineups</li>
          </ul>
          <p>
            Industry analysts note a 15% year-over-year increase in vinyl sales, suggesting continued
            consumer interest in physical media alongside digital consumption.
          </p>
        `,
      },
      {
        id: "stock-analysis",
        title: "Stock Analysis",
        order: 5,
        content: `
          <h3>Sector Performance and Notable Movers</h3>
          <p>
            Technology sector led gains with semiconductor manufacturers posting strong earnings.
            The sector's resilience despite supply chain concerns signals robust demand for
            next-generation computing infrastructure.
          </p>
          <p>
            <strong>Top Performers:</strong>
          </p>
          <ul>
            <li>Semiconductor ETF (SMH) +2.4%</li>
            <li>Clean Energy sector showed strength on policy news</li>
            <li>Healthcare stocks mixed following regulatory announcements</li>
          </ul>
          <p>
            <strong>Analyst Outlook:</strong> Market sentiment remains cautiously optimistic heading
            into earnings season. Volatility expected to continue as macroeconomic data releases
            provide clearer picture of growth trajectory.
          </p>
        `,
      },
      {
        id: "daily-summary",
        title: "Daily Summary",
        order: 6,
        content: `
          <h3>Key Takeaways</h3>
          <p>
            Today's developments reflect a complex global landscape balancing economic recovery,
            geopolitical tensions, and evolving cultural trends. Several themes emerged:
          </p>
          <ol>
            <li><strong>Policy Cooperation:</strong> Bipartisan infrastructure progress suggests potential
            for collaborative governance despite polarization</li>
            <li><strong>Economic Signals:</strong> Mixed market performance indicates uncertainty about
            inflation trajectory and monetary policy responses</li>
            <li><strong>Cultural Shifts:</strong> Entertainment industry adapting to streaming-first
            consumer behavior with innovative distribution models</li>
            <li><strong>Technological Momentum:</strong> Continued strength in tech sector points to
            sustained digital transformation across industries</li>
          </ol>
          <p>
            These interconnected narratives demonstrate how political decisions, market forces, and
            cultural production shape our collective experience.
          </p>
        `,
      },
      {
        id: "outlook",
        title: "Outlook",
        order: 7,
        content: `
          <h3>What May Come Next</h3>
          <p>
            <strong>Short-term (Next 48-72 hours):</strong>
          </p>
          <ul>
            <li>Key economic data releases will test market resilience</li>
            <li>Ongoing diplomatic discussions may yield progress on trade frameworks</li>
            <li>Entertainment industry poised for major announcements at upcoming events</li>
          </ul>
          <p>
            <strong>Medium-term (Next 2-4 weeks):</strong>
          </p>
          <ul>
            <li>Earnings season begins, providing clarity on corporate health</li>
            <li>Climate negotiations continue ahead of international summit</li>
            <li>Technology product launches expected to drive consumer sentiment</li>
          </ul>
          <p>
            <strong>Themes to Watch:</strong> The interplay between monetary policy, geopolitical
            stability, and technological innovation will likely define the next phase of global
            development. Markets appear positioned for continued volatility as these forces interact.
          </p>
        `,
      },
    ],
  };
}

/**
 * Mocked set of dates that have diary entries
 * In production, this would query the database for available dates
 */
const AVAILABLE_DATES = new Set([
  "2026-01-01",
  "2026-01-02",
  "2026-01-03",
  "2026-01-04",
  "2026-01-05",
  "2026-01-06", // Today
]);

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ date: string }> }
) {
  const { date } = await params;

  // Validate date format (basic check)
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) {
    return NextResponse.json(
      { error: "Invalid date format. Use YYYY-MM-DD" },
      { status: 400 }
    );
  }

  // Check if diary entry exists for this date
  if (!AVAILABLE_DATES.has(date)) {
    return NextResponse.json(
      { error: "No diary entry found for this date" },
      { status: 404 }
    );
  }

  // Simulate network delay for realism
  await new Promise((resolve) => setTimeout(resolve, 100));

  const diaryEntry = generateMockedDiaryEntry(date);

  return NextResponse.json({ data: diaryEntry });
}
