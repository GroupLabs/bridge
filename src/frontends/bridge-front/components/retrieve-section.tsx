import React from 'react'
import { Section } from '@/components/section'
import { SearchResults } from '@/components/search-results'
import {
  SearchResultItem,
  SearchResult,
  SearchResults as SearchResultsType
} from '@/lib/types'

interface RetrieveSectionProps {
  data: SearchResultsType
}

const transformSearchResults = (items: SearchResultItem[]): SearchResult[] => {
  return items.map(item => ({
    id: item.url, // Assuming URL can uniquely identify each item, otherwise generate or fetch an appropriate ID
    score: 0, // Placeholder score, as the original data doesn't include a score
    text: item.content // Assuming content is the equivalent of text
  }))
}

const RetrieveSection: React.FC<RetrieveSectionProps> = ({ data }) => {
  const transformedResults = transformSearchResults(data.results)
  return (
    <Section title="Sources">
      <SearchResults results={transformedResults} />
    </Section>
  )
}

export default RetrieveSection
