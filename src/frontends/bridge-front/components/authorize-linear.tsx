// components/AuthorizeLinear.tsx
'use client';

import React, { useState } from 'react';
import Nango from '@nangohq/frontend';

interface Issue {
    id: string;
    title: string;
    status: string;
    createdAt: string;
}

const AuthorizeLinear: React.FC = () => {
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
        <div>
            <button onClick={handleAuth} disabled={loading}>
                {loading ? 'Authorizing and Fetching Issues...' : 'Authorize with Linear and Fetch Issues'}
            </button>
            {error && <p>{error}</p>}
            {issues.length > 0 && (
                <div>
                    <h2>Linear Issues</h2>
                    <ul>
                        {issues.map((issue) => (
                            <li key={issue.id}>
                                {issue.title} - {issue.status} (Created at: {new Date(issue.createdAt).toLocaleString()})
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </div>
    );
};

export default AuthorizeLinear;