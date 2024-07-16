import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  try {
    const data = await req.formData();
    const file: File | null = data.get("file") as unknown as File;

    if (!file) {
      return new NextResponse("No file uploaded", { status: 400 });
    }

    const formData = new FormData();
    const date = new Date().toISOString().split('.')[0];
    const filename = `LinearIssues::${date}.json`;
    formData.append("file", new File([file], filename, { type: file.type }), filename);
    formData.append("c_type", "linear");

    const response = await fetch(`${process.env.BRIDGE_URL}/load`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      return new NextResponse("Failed to upload file", { status: response.status });
    }

    const responseData = await response.json();

    return NextResponse.json({ success: true, response: responseData });
  } catch (error) {
    console.error("Error uploading file:", error);
    return new NextResponse("Server error", { status: 500 });
  }
}