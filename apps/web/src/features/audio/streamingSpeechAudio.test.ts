import { describe, expect, it } from "vitest";
import { readSpeechFrames } from "./streamingSpeechAudio";

const encode = (event: unknown) => new TextEncoder().encode(JSON.stringify(event) + "\n");
const audio = { type: "audio", audioBase64: "AAAAAA==", sampleRate: 24_000, text: "a", alignment: [{char:"a",startMs:0,endMs:50}] };

describe("incremental speech audio", () => {
  it("yields playable PCM while the network response is still open", async () => {
    let network!: ReadableStreamDefaultController<Uint8Array>;
    const response = new Response(new ReadableStream({ start(controller) { network = controller; } }));
    const frames = readSpeechFrames(response, new AbortController().signal);
    network.enqueue(encode(audio));
    const first = await frames.next();
    expect(first.done).toBe(false);
    expect(first.value?.blob.type).toBe("audio/pcm");
    expect(first.value?.blob.size).toBe(4);
    expect(first.value?.visemes?.[0].mouth).toBe("aa");
    network.enqueue(encode({type:"done"}));
    expect((await frames.next()).done).toBe(true);
  });

  it("handles split network frames and preserves their order", async () => {
    const bytes = encode(audio);
    const response = new Response(new ReadableStream({ start(controller) {
      controller.enqueue(bytes.slice(0, 19)); controller.enqueue(bytes.slice(19));
      controller.enqueue(encode({...audio,text:"b"})); controller.enqueue(encode({type:"done"})); controller.close();
    } }));
    const result = [];
    for await (const frame of readSpeechFrames(response, new AbortController().signal)) result.push(frame.text);
    expect(result).toEqual(["a", "b"]);
  });

  it("rejects truncated audio instead of completing silently", async () => {
    const frames = readSpeechFrames(new Response(encode(audio)), new AbortController().signal);
    await frames.next();
    await expect(frames.next()).rejects.toThrow("before completion");
  });

  it("cancels a pending network read when interrupted", async () => {
    const controller = new AbortController();
    const frames = readSpeechFrames(new Response(new ReadableStream({})), controller.signal);
    const pending = frames.next();
    controller.abort();
    await expect(pending).rejects.toMatchObject({name:"AbortError"});
  });

  it("rejects malformed PCM and explicit vendor failure", async () => {
    for (const event of [{...audio,audioBase64:"AA=="},{type:"error"}]) {
      const frames = readSpeechFrames(new Response(encode(event)), new AbortController().signal);
      await expect(frames.next()).rejects.toThrow();
    }
  });
});
