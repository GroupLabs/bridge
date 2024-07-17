'use server'

export async function uploadFile(data: FormData) {
    const bridgeUrl = process.env.BRIDGE_URL;
  
    if (!bridgeUrl) {
      throw new Error("BRIDGE_URL is not defined");
    }
  
    const response = await fetch(`${bridgeUrl}/load`, {
      method: "POST",
      body: data,
    });
  
    return response;
  }