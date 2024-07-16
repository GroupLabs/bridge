// app/api/fetch-issues/route.ts
import { NextRequest, NextResponse } from 'next/server';

export async function POST(req: NextRequest) {
    const { connectionId } = await req.json();

    try {
        const response = await fetch(`https://api.nango.dev/records`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${process.env.NEXT_PUBLIC_NANGO_SECRET_KEY}`,
                'Provider-Config-Key': process.env.NEXT_PUBLIC_NANGO_INTEGRATION_ID,
                'Connection-Id': connectionId,
                'Content-Type': 'application/json'
            } as HeadersInit
        });

        if (!response.ok) {
            throw new Error('Failed to fetch issues from Nango');
        }

        const data = await response.json();
        return NextResponse.json({ nodes: data.records });
    } catch (error) {
        console.error('Error fetching issues:', error);
        return NextResponse.json({ error: 'Error fetching issues' }, { status: 500 });
    }
}