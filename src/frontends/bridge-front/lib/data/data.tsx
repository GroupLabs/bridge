import {
  CheckCircledIcon,
  CircleIcon,
  CrossCircledIcon,
  StopwatchIcon,
} from "@radix-ui/react-icons"

export const labels = [
  // file types
  {
    value: "file",
    label: "File",
  },
  // 3rd party integrations
  {
    value: "linear",
    label: "Linear",
  },
  // {
  //   value: "slack",
  //   label: "Slack",
  // },
  // // database types
  // {
  //   value: "postgres",
  //   label: "Postgres",
  // },
  // {
  //   value: "mysql",
  //   label: "MySQL",
  // },
  // {
  //   value: "mongodb",
  //   label: "MongoDB",
  // },
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
