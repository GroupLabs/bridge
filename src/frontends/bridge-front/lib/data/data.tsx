import {
  ArrowDownIcon,
  ArrowRightIcon,
  ArrowUpIcon,
  CheckCircledIcon,
  CircleIcon,
  CrossCircledIcon,
  QuestionMarkCircledIcon,
  StopwatchIcon,
} from "@radix-ui/react-icons"

export const labels = [
  // file types
  {
    value: "csv",
    label: "CSV",
  },
  {
    value: "pdf",
    label: "PDF",
  },
  {
    value: "txt",
    label: "TXT",
  },
  // 3rd party integrations
  {
    value: "slack",
    label: "Slack",
  },
  // database types
  {
    value: "postgres",
    label: "Postgres",
  },
  {
    value: "mysql",
    label: "MySQL",
  },
  {
    value: "mongodb",
    label: "MongoDB",
  },
]

export const statuses = [
  {
    value: "PENDING",
    label: "Pending",
    icon: CircleIcon,
  },
  {
    value: "STARTED",
    label: "In Progress",
    icon: StopwatchIcon,
  },
  {
    value: "SUCCESS",
    label: "Done",
    icon: CheckCircledIcon,
  },
  {
    value: "FAILURE",
    label: "Canceled",
    icon: CrossCircledIcon,
  },
]

// export const priorities = [
//   {
//     label: "Low",
//     value: "low",
//     icon: ArrowDownIcon,
//   },
//   {
//     label: "Medium",
//     value: "medium",
//     icon: ArrowRightIcon,
//   },
//   {
//     label: "High",
//     value: "high",
//     icon: ArrowUpIcon,
//   },
// ]
