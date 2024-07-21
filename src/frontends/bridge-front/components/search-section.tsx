'use client'

import { SearchResultsWeb } from './search-results-web'
import { SearchResultsBridge } from './search-results-bridge'
import { SearchSkeleton } from './search-skeleton'
import { Section } from './section'
import { ToolBadge } from './tool-badge'
import type { SearchResults as TypeSearchResults } from '@/lib/types'
import type { BridgeSearchResults } from '@/lib/types'
import { StreamableValue, useStreamableValue } from 'ai/rsc'

export type SearchSectionProps = {
  resultWeb?: StreamableValue<string>
  resultBridge?: StreamableValue<string>
}

export function SearchSection({ resultWeb, resultBridge }: SearchSectionProps) {
  const [dataWeb, errorWeb, pendingWeb] = useStreamableValue(resultWeb)
  const [dataBridge, errorBridge, pendingBridge] = useStreamableValue(resultBridge)
  const searchResultsWeb: TypeSearchResults = dataWeb ? JSON.parse(dataWeb) : { query: '', results: [] }
  const searchResultsBridge: BridgeSearchResults = dataBridge ? JSON.parse(dataBridge) : { query: '', results: [] }

  const hasWebResults = !pendingWeb && dataWeb
  const hasBridgeResults = !pendingBridge && dataBridge

  return (
    <div>
      {hasWebResults ? (
        <>
          <Section size="sm" className="pt-2 pb-0">
            <ToolBadge tool="search">{`${searchResultsWeb.query}`}</ToolBadge>
          </Section>
          <Section title="Web Results">
            <SearchResultsWeb results={searchResultsWeb.results} />
          </Section>
        </>
      ) : null}
      {hasBridgeResults ? (
        <>
          <Section size="sm" className="pt-2 pb-0">
            <ToolBadge tool="search">{`${searchResultsBridge.query}`}</ToolBadge>
          </Section>
          <Section title="Bridge Results">
            <SearchResultsBridge results={searchResultsBridge.results} />
          </Section>
        </>
      ) : null}
      {!hasWebResults && !hasBridgeResults ? (
        <Section className="pt-2 pb-0">
          <SearchSkeleton />
        </Section>
      ) : null}
    </div>
  )
}