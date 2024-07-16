'use server'
import { NextRequest, NextResponse } from 'next/server';
import { Nango } from '@nangohq/node';

export async function POST(req: NextRequest) {
    const { connectionId } = await req.json();
    console.log('Received connectionId:', connectionId);

    try {
        const nango = new Nango({ secretKey: process.env.NANGO_SECRET_KEY as string });

        const records = await nango.listRecords({
            providerConfigKey: process.env.NEXT_PUBLIC_LINEAR_INTEGRATION_ID as string,
            connectionId: connectionId,
            model: 'LinearIssue'
        });

        return NextResponse.json({ nodes: records.records });
    } catch (error) {
        console.error('Error in proxy API route:', error);
        return NextResponse.json({ error: 'Error fetching issues via proxy' }, { status: 500 });
    }
}