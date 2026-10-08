import {expect, test} from "vitest";
import {RuntimeMeasurements} from "./runtimeMeasurements";
test("measures real frame samples and does not report inactive rendering", () => {
 const meter = new RuntimeMeasurements();
 expect(meter.snapshot(0).fps).toBeNull();
 for (let i=0;i<60;i++) meter.recordFrame(1/60, 1000);
 expect(meter.snapshot(1000).fps).toBeCloseTo(60);
 expect(meter.snapshot(1000).frameP95Ms).toBeCloseTo(16.67);
 expect(meter.snapshot(5000).fps).toBeNull();
});
test("records only the first playback start for the current turn", () => {
 const meter = new RuntimeMeasurements();
 const old = meter.beginTurn(10);
 const current = meter.beginTurn(100);
 meter.speechStarted(old, "stale", 200);
 expect(meter.snapshot().speechOnsetMs).toBeNull();
 meter.speechStarted(current, "elevenlabs", 550);
 meter.speechStarted(current, "duplicate", 700);
 expect(meter.snapshot().speechOnsetMs).toBe(450);
 expect(meter.snapshot().speechProvider).toBe("elevenlabs");
});
