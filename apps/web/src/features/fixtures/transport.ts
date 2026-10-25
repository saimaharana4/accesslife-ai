import { createFixtureRounds, fixtureWinner } from "./fixture-data.ts";
import type {
  AdvanceResult,
  FixtureAnswer,
  FixtureGameInfo,
  FixtureRound,
  FixtureSeed,
  FixtureStory,
  FixtureTransport,
  StartResult,
} from "./types.ts";

type LocalGame = {
  info: FixtureGameInfo;
  rounds: FixtureRound[];
  current: number;
  answers: Map<string, FixtureAnswer>;
  retries: Set<string>;
  answerKeys: Map<string, string>;
  advances: Map<string, { roundId: string; result: AdvanceResult }>;
};

export class FixtureFailure extends Error {
  readonly kind: "retry" | "expired" | "interrupted";
  constructor(kind: "retry" | "expired" | "interrupted", message: string) {
    super(message);
    this.kind = kind;
  }
}

function pause(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new FixtureFailure("interrupted", "Fixture request cancelled."));
      return;
    }
    const aborted = () => {
      clearTimeout(timer);
      reject(new FixtureFailure("interrupted", "Fixture request cancelled."));
    };
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", aborted);
      resolve();
    }, ms);
    signal?.addEventListener("abort", aborted, { once: true });
  });
}

/** In-memory UI adapter only. It has no network, cookies, browser storage or backend. */
export class InMemoryFixtureTransport implements FixtureTransport {
  private games = new Map<string, LocalGame>();
  private starts = new Map<
    string,
    { signature: string; result: StartResult }
  >();
  private sequence = 0;
  private readonly latency: number;
  constructor(latency = 260) {
    this.latency = latency;
  }

  async start(
    seed: FixtureSeed,
    story: FixtureStory,
    key: string,
    signal?: AbortSignal,
  ): Promise<StartResult> {
    const signature = `${seed.id}:${story}`;
    let record = this.starts.get(key);
    if (record && record.signature !== signature)
      throw new FixtureFailure(
        "retry",
        "Fixture request key belongs to different input.",
      );
    if (!record) {
      let result: StartResult;
      if (story === "empty" || story === "partial")
        result = { kind: story, available: story === "empty" ? 0 : 3 };
      else {
        const id = `fixture-game-${++this.sequence}`;
        const rounds = createFixtureRounds(story === "long-title");
        const info: FixtureGameInfo = { id, seed, total: 5, story };
        this.games.set(id, {
          info,
          rounds,
          current: 0,
          answers: new Map(),
          retries: new Set(),
          answerKeys: new Map(),
          advances: new Map(),
        });
        result = { kind: "ready", game: info, round: rounds[0] };
      }
      record = { signature, result };
      this.starts.set(key, record);
    }
    await pause(this.latency, signal);
    return record.result;
  }

  private game(id: string) {
    const game = this.games.get(id);
    if (!game)
      throw new FixtureFailure(
        "expired",
        "This local fixture no longer exists. Refreshing clears in-memory fixture progress.",
      );
    return game;
  }

  async answer(
    gameId: string,
    roundId: string,
    choiceId: string,
    key: string,
    signal?: AbortSignal,
  ): Promise<FixtureAnswer> {
    const game = this.game(gameId);
    const round = game.rounds[game.current];
    if (round?.id !== roundId)
      throw new FixtureFailure("retry", "That fixture round is not current.");
    const choice = round.choices.find((candidate) => candidate.id === choiceId);
    if (!choice)
      throw new FixtureFailure(
        "retry",
        "That choice is not in the fixture round.",
      );
    const signature = `${roundId}:${choiceId}`;
    if (game.answerKeys.has(key) && game.answerKeys.get(key) !== signature)
      throw new FixtureFailure(
        "retry",
        "Fixture answer key belongs to different input.",
      );
    game.answerKeys.set(key, signature);
    const saved = game.answers.get(roundId);
    if (saved && saved.choiceId !== choiceId)
      throw new FixtureFailure(
        "retry",
        "A different answer is already accepted for this fixture round.",
      );
    const winner = fixtureWinner(round);
    const answer = saved ?? {
      roundId,
      ordinal: round.ordinal,
      choiceId,
      winnerId: winner.id,
      correct: choice.id === winner.id,
      winnerTitle: winner.title,
      selectedTitle: choice.title,
    };
    game.answers.set(roundId, answer);
    // Accept first, then deliberately lose one response in the retry story.
    const loseResponse =
      game.info.story === "retry" &&
      game.current === 0 &&
      !game.retries.has(roundId);
    if (loseResponse) game.retries.add(roundId);
    await pause(this.latency, signal);
    if (loseResponse)
      throw new FixtureFailure(
        "retry",
        "The fixture accepted your answer, then simulated a lost response. Retry the same answer; it will not add another point.",
      );
    return answer;
  }

  async advance(
    gameId: string,
    roundId: string,
    key: string,
    signal?: AbortSignal,
  ): Promise<AdvanceResult> {
    const game = this.game(gameId);
    const saved = game.advances.get(key);
    if (saved) {
      if (saved.roundId !== roundId)
        throw new FixtureFailure(
          "retry",
          "Fixture advance key belongs to another round.",
        );
      await pause(this.latency, signal);
      return saved.result;
    }
    if (game.rounds[game.current]?.id !== roundId || !game.answers.has(roundId))
      throw new FixtureFailure(
        "retry",
        "Answer the current fixture round before advancing.",
      );
    const result: AdvanceResult =
      game.current === 4
        ? { kind: "complete" }
        : { kind: "round", round: game.rounds[++game.current] };
    game.advances.set(key, { roundId, result });
    await pause(this.latency, signal);
    return result;
  }
}
