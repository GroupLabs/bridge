// app/api/authorize/route.ts
import { NextRequest, NextResponse } from "next/server";
import Nango from '@nangohq/frontend';

export async function POST(req: NextRequest) {
    const nango = new Nango({ publicKey: process.env.NEXT_PUBLIC_NANGO_PUBLIC_KEY as string });

    try {
        const result = await nango.auth(process.env.NEXT_PUBLIC_NANGO_INTEGRATION_ID as string, 'test-connection-id');
        return NextResponse.json({ success: true, data: result });
    } catch (error) {
        console.error('Authorization failed:', error);
        return NextResponse.json({ success: false, message: 'Authorization failed' }, { status: 500 });
    }
}