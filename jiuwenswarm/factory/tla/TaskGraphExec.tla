---------------------------- MODULE TaskGraphExec ----------------------------
(***************************************************************************)
(* How the software factory executes a task graph.                        *)
(*                                                                         *)
(* The rules come from the factory code and from the execution contract   *)
(* the planner hands to the downstream scheduler with every graph:        *)
(*   - a node starts only when every predecessor is done and it has       *)
(*     attempts left (scheduler.py: next_work, admitted, charge);         *)
(*   - a node is done only when its work succeeded and its output checks  *)
(*     passed; a failure of either sends the work back for another        *)
(*     attempt, or fails the node when none is left (node_check.py);      *)
(*   - at most MaxParallel nodes are active at once, and an active node   *)
(*     holds its exclusive resources (the owned checkout when it writes   *)
(*     code, the builder when it builds) until it finishes.               *)
(*                                                                         *)
(* Work and checks finish in one step here: while either runs the node is *)
(* active and holds its resources, which is all any other node can see.   *)
(*                                                                         *)
(* A plan instantiates the constants (tla_check.py writes the module).    *)
(* TLC then explores every interleaving of starts and outcomes.           *)
(*                                                                         *)
(* Liveness is proven by safety checks, which TLC runs much faster:       *)
(*   Termination: every step strictly decreases Rank, a natural number,   *)
(*     so every run takes finitely many steps and then halts;             *)
(*   NoStuck: a run halts only delivered or with a failed node.           *)
(* Together: every run ends delivered or with a reported failure. With    *)
(* Cooperative (a node's last allowed attempt succeeds) HaltsDelivered    *)
(* adds that every run ends delivered.                                    *)
(***************************************************************************)
EXTENDS Naturals, FiniteSets

CONSTANTS
    Nodes,        \* node ids of the plan
    Preds,        \* [Nodes -> SUBSET Nodes]: predecessors (data and ordering)
    Deliver,      \* the deliver node: the one leaf
    Limit,        \* [Nodes -> Nat]: attempts a node may start
    Exclusive,    \* [Nodes -> SUBSET resource names] held while active
    MaxParallel,  \* nodes the scheduler runs at once
    Cooperative   \* TRUE: the last allowed attempt of a node does not fail

ASSUME /\ Deliver \in Nodes
       /\ Preds \in [Nodes -> SUBSET Nodes]
       /\ Limit \in [Nodes -> Nat]
       /\ MaxParallel \in Nat \ {0}
       /\ Cooperative \in BOOLEAN

VARIABLES st, att
vars == <<st, att>>

Phases == {"waiting", "active", "done", "failed"}
Active == {n \in Nodes : st[n] = "active"}
Held == UNION {Exclusive[n] : n \in Active}

Init == /\ st = [n \in Nodes |-> "waiting"]
        /\ att = [n \in Nodes |-> 0]

CanStart(n) == /\ st[n] = "waiting"
               /\ \A p \in Preds[n] : st[p] = "done"
               /\ att[n] < Limit[n]
               /\ Cardinality(Active) < MaxParallel
               /\ Exclusive[n] \cap Held = {}

Start(n) == /\ CanStart(n)
            /\ st' = [st EXCEPT ![n] = "active"]
            /\ att' = [att EXCEPT ![n] = @ + 1]

\* Work succeeded and every output check passed.
Succeed(n) == /\ st[n] = "active"
              /\ st' = [st EXCEPT ![n] = "done"]
              /\ UNCHANGED att

\* Work failed or a check failed: another attempt if one is left, otherwise
\* the node fails and the run escalates. Under Cooperative the environment
\* may not fail a node's last attempt.
SendBack(n) == /\ st[n] = "active"
               /\ ~Cooperative \/ att[n] < Limit[n]
               /\ st' = [st EXCEPT ![n] = IF att[n] < Limit[n] THEN "waiting" ELSE "failed"]
               /\ UNCHANGED att

Step == \E n \in Nodes : Start(n) \/ Succeed(n) \/ SendBack(n)

Delivered == st[Deliver] = "done"
Failed == \E n \in Nodes : st[n] = "failed"

\* Step is enabled. Written out so TLC evaluates a plain state predicate.
CanStep == Active # {} \/ \E n \in Nodes : CanStart(n)

\* Nothing can move any more. Stuttering here keeps TLC's deadlock report out
\* of the way; NoStuck says which endings are acceptable.
Halt == ~CanStep /\ UNCHANGED vars

Next == Step \/ Halt

Spec == Init /\ [][Next]_vars

-----------------------------------------------------------------------------
(* Progress measure: attempts left weigh 2, waiting 1, active 2, ended 0.  *)
(* Start: -2 for the attempt, +1 waiting->active. Succeed: -2. SendBack:  *)
(* -1 to waiting, -2 to failed. Every step decreases it.                  *)

PhaseWeight(p) == CASE p = "waiting" -> 1 [] p = "active" -> 2 [] OTHER -> 0
RECURSIVE SumOver(_, _)
SumOver(f, S) == IF S = {} THEN 0 ELSE LET x == CHOOSE y \in S : TRUE IN f[x] + SumOver(f, S \ {x})
Rank == SumOver([n \in Nodes |-> 2 * (Limit[n] - att[n]) + PhaseWeight(st[n])], Nodes)

-----------------------------------------------------------------------------
(* Safety: true in every reachable state. *)

TypeOK == /\ st \in [Nodes -> Phases]
          /\ att \in [Nodes -> Nat]

\* A node is active or done only after all its predecessors are done.
DependencyOrder == \A n \in Nodes :
    st[n] \in {"active", "done"} => \A p \in Preds[n] : st[p] = "done"

\* No two active nodes hold the same resource (one writer of the checkout,
\* one user of the builder).
ExclusiveResources == \A m, n \in Active : m # n => Exclusive[m] \cap Exclusive[n] = {}

ParallelBound == Cardinality(Active) <= MaxParallel

AttemptBound == \A n \in Nodes : att[n] <= Limit[n]

\* When nothing can move, the run has delivered or has a failed node to report.
NoStuck == ~CanStep => (Delivered \/ Failed)

\* Delivery means every step is done: its work succeeded and its checks passed.
DeliveredMeansAllDone == Delivered => \A n \in Nodes : st[n] = "done"

\* Cooperative run: when nothing can move, the run has delivered.
HaltsDelivered == ~CanStep => Delivered

(* Termination, as an action property: every step decreases Rank. *)
Termination == [][Rank' < Rank]_vars

=============================================================================
