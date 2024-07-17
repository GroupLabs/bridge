// @ts-nocheck

import React from 'react'
import { Section } from '@/components/section'
import { SearchResultsWeb } from '@/components/search-results-web'
import { SearchResults as SearchResultsType } from '@/lib/types'

interface RetrieveSectionProps {
  data: SearchResultsType
}

const RetrieveSection: React.FC<RetrieveSectionProps> = ({ data }) => {
  return (
    <Section title="Sources">
      <SearchResultsWeb results={data.results} />
    </Section>
  )
}

export default RetrieveSection
