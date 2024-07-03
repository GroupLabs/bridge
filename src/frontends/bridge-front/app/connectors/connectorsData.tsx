import githubimg from '@/public/images/github.svg'
import slackimg from '@/public/images/slack.svg'
import office365img from '@/public/images/office365.png'
import googledriveimg from '@/public/images/googledrive.svg'
import sapimg from '@/public/images/sap.svg'
import workdayimg from '@/public/images/workday.svg'
import salesforceimg from '@/public/images/salesforce.svg'

const connectors = [
  {
    title: 'Slack',
    img: slackimg,
    active: false
  },
  {
    title: 'Office 365',
    img: office365img,
    active: true
  },
  {
    title: 'Google workspace',
    img: googledriveimg,
    active: false
  },
  {
    title: 'SAP',
    img: sapimg,
    active: false
  },
  {
    title: 'Workday',
    img: workdayimg,
    active: true
  },
  {
    title: 'Salesforce',
    img: salesforceimg,
    active: false
  },
  {
    title: 'Github',
    img: githubimg,
    active: true
  }
]

export default connectors
