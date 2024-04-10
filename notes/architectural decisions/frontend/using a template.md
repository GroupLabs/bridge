> April 8, 2024 - Noel

For speed, we're opting to fork [Mckay Wrigley's Chatbot-UI](https://github.com/mckaywrigley/chatbot-ui). However, we noticed that there is unneccessary complexity. This comes from how the UI manages different contextual data like LLMs, prompts, tools, and so forth. Furthermore, it requires the use of a lightweight deployment of supabase for user management. While this could be useful, Our goal is to reduce operational complexity in areas that are not our forte. We also estimate significant effort to unbind supabase from the UI.This complexity overhead may become a challenge in the future.

Instead, we are considering integrating with user management platforms that can provide other forms of user management like SSO, etc. We're considering products like: Clerk, WorkOS.

Further, it makes a lot of sense to nuke the current frontend in favor of a [minimal project](https://sdk.vercel.ai/docs/getting-started) and add in interesting and useful features over time.My understanding is that we should be able to port over the changes we make to the current template, to the new UI without much hassle.

Other things to look at:
- https://vercel.com/blog/ai-sdk-3-generative-ui