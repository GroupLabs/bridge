// components/add-data-linear-tasks.tsx
'use client';

import React, { useState } from 'react';
import Nango from '@nangohq/frontend';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { Badge } from '@/components/ui/badge';

interface Issue {
    id: string;
    title: string;
    status: string;
    createdAt: string;
}

export const AddDataLinearTasks: React.FC = () => {
    const [issues, setIssues] = useState<Issue[]>([]);
    const [loading, setLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);

    const handleAuth = async () => {
        setLoading(true);
        const nango = new Nango({ publicKey: process.env.NEXT_PUBLIC_NANGO_PUBLIC_KEY as string });

        try {
            const authResult = await nango.auth(process.env.NEXT_PUBLIC_NANGO_INTEGRATION_ID as string, 'test-connection-id');

            // Assuming authResult has a connectionId to use for fetching data
            const connectionId = authResult.connectionId;
            if (!connectionId) {
                throw new Error('No connection ID received from Nango');
            }

            // Fetch issues from the backend using the connectionId
            const issuesResponse = await fetch(`/api/proxy`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ connectionId })
            });

            if (!issuesResponse.ok) {
                const errorText = await issuesResponse.text();
                console.error('Error fetching issues from backend:', errorText);
                throw new Error('Failed to fetch issues from backend');
            }

            const issuesData = await issuesResponse.json();
            setIssues(issuesData.nodes);
            setLoading(false);
        } catch (error) {
            console.error('Authorization or fetching issues failed:', error);
            setError('Authorization or fetching issues failed. Please try again.');
            setLoading(false);
        }
    };

    return (
        <div className="">
            <Button onClick={handleAuth} disabled={loading} variant="outline" className="mb-4">
                {loading ? 'Authorizing and Fetching Issues...' : 'Authorize with Linear and Fetch Issues'}
            </Button>
            {error && <p>{error}</p>}
            
            {issues.length > 0 && (
                <>
                    <h4 className="mb-4 text-sm font-medium leading-none">Fetched Linear Issues</h4>
                    <ScrollArea className="h-72 rounded-md border">
                        <div className="p-4">
                            
                            {issues.map((issue) => (
                                <React.Fragment key={issue.id}>
                                    <div className="font-medium text-sm py-1">
                                        <Badge variant="outline">{issue.status}</Badge>
                                    </div>
                                    <div className="flex items-center text-sm px-2">
                                        {issue.title}
                                    </div>
                                    <div className="text-xs text-muted-foreground px-2">
                                        {new Date(issue.createdAt).toLocaleString()}
                                    </div>
                                    <Separator className="my-2" />
                                </React.Fragment>
                            ))}
                        </div>
                    </ScrollArea>
                    <Button disabled={loading} variant="secondary" className="mt-4">
                        {"Submit"}
                    </Button>
                </>
            )}
        </div>
    );
};