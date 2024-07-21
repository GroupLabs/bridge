// app/api/fetchfiles/route.ts
import { NextResponse } from 'next/server';

export async function GET() {
  const url = process.env.BRIDGE_URL;

  if (!url) {
    return NextResponse.json({ error: 'BRIDGE_URL is not defined' }, { status: 500 });
  }

  try {
    const response = await fetch(`${url}/retrieve_ids/text_chunk/`, {
      cache: 'no-store'
    });
    const data = await response.json();

    if (!data || !Array.isArray(data.ids)) {
      return NextResponse.json({ ids: [] });
    }

    const formattedData = data.ids.map(([id, label, _size]: [string, string, number]) => ({ value: id, label }));
    return NextResponse.json({ ids: formattedData });
  } catch (error) {
    console.error("Error fetching files:", error);
    return NextResponse.json({ error: 'Error fetching files' }, { status: 500 });
  }
}