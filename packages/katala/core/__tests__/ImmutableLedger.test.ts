import { describe, it, expect, beforeEach } from "vitest";
import { ImmutableLedger, LedgerEntry } from "../ImmutableLedger";

describe("ImmutableLedger", () => {
  let ledger: ImmutableLedger;

  beforeEach(() => {
    ledger = new ImmutableLedger();
  });

  describe("append", () => {
    it("should create a genesis entry with previousHash '0'", async () => {
      const entry = await ledger.append("test", { foo: "bar" });
      expect(entry.previousHash).toBe("0");
      expect(entry.hash).toBeTruthy();
      expect(entry.eventType).toBe("test");
      expect(entry.payload).toEqual({ foo: "bar" });
      expect(entry.id).toBeTruthy();
      expect(entry.timestamp).toBeTruthy();
    });

    it("should link entries via previousHash", async () => {
      const first = await ledger.append("a", {});
      const second = await ledger.append("b", {});
      expect(second.previousHash).toBe(first.hash);
    });

    it("should produce unique hashes for different entries", async () => {
      const a = await ledger.append("x", { v: 1 });
      const b = await ledger.append("x", { v: 2 });
      expect(a.hash).not.toBe(b.hash);
    });
  });

  describe("verify", () => {
    it("should return true for an empty chain", async () => {
      expect(await ledger.verify()).toBe(true);
    });

    it("should return true for a valid chain", async () => {
      await ledger.append("e1", { a: 1 });
      await ledger.append("e2", { b: 2 });
      await ledger.append("e3", { c: 3 });
      expect(await ledger.verify()).toBe(true);
    });

    it("should detect payload tampering", async () => {
      await ledger.append("e1", { a: 1 });
      await ledger.append("e2", { b: 2 });

      // Tamper with the first entry's payload
      const history = ledger.getHistory();
      const tampered = history[history.length - 1] as LedgerEntry & Record<string, unknown>;
      (tampered.payload as Record<string, unknown>).a = 999;

      expect(await ledger.verify()).toBe(false);
    });

    it("should detect hash tampering", async () => {
      await ledger.append("e1", {});
      await ledger.append("e2", {});

      // Tamper with a hash — breaks the chain linkage
      const history = ledger.getHistory();
      const oldest = history[history.length - 1];
      oldest.hash = "deadbeef";

      expect(await ledger.verify()).toBe(false);
    });
  });

  describe("getHistory", () => {
    it("should return entries in reverse chronological order", async () => {
      await ledger.append("first", {});
      await ledger.append("second", {});
      await ledger.append("third", {});

      const history = ledger.getHistory();
      expect(history).toHaveLength(3);
      expect(history[0].eventType).toBe("third");
      expect(history[2].eventType).toBe("first");
    });

    it("should respect the limit parameter", async () => {
      await ledger.append("a", {});
      await ledger.append("b", {});
      await ledger.append("c", {});

      const history = ledger.getHistory(2);
      expect(history).toHaveLength(2);
      expect(history[0].eventType).toBe("c");
      expect(history[1].eventType).toBe("b");
    });

    it("should return empty array for empty chain", () => {
      expect(ledger.getHistory()).toEqual([]);
    });
  });
});
