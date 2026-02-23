# active-inference-tutorial — Ground Truth Review

Paper: active-inference-tutorial
Item key: SCPXVBLY
Total tables: 8 (1 artifact + 7 data)

---

## table_0 (p1) — ARTIFACT: unknown [0 cols × 0 rows]

- **Caption:** c MRC Cognition and Brain Sciences Unit, University of Cambridge, Cambridge, UK
- **Notes:** Artifact: article_info_box, not a data table
- **Verified:** true

(No table to render — headers and rows are empty.)

---

## table_1 (p15) — Table 1 Model variables. [3 cols × 6 rows]

- **Caption:** Table 1 Model variables.
- **Notes:** Table continues on next page. The header 'Model specification for explore-exploit task (described in detail Section 3)' spans column 3. Row content with numbered lists represents multi-line cell content joined with spaces; newlines used here for readability only.
- **Verified:** true

<table>
<thead><tr>
<th>Model variable*</th>
<th>General definition</th>
<th>Model specification for explore–exploit task (described in detail Section 3)</th>
</tr></thead>
<tbody>
<tr>
<td>oτ</td>
<td>Observable outcomes at time τ.</td>
<td>Outcome modalities:<br>1. Hints (no hint, hint-left, hint-right)<br>2. Reward (start, lose, win)<br>3. Observed behavior (start, take hint, choose left, choose right)</td>
</tr>
<tr>
<td>sτ</td>
<td>Hidden states at time τ. One vector of possible state values for each state factor (i.e., each independent set of states; e.g., visual vs. auditory states).</td>
<td>Hidden state factors:<br>1. Context (left machine is better vs. right machine is better)<br>2. Choices (start, take hint, choose left, choose right)</td>
</tr>
<tr>
<td>π</td>
<td>A vector encoding the distribution over policies reflecting the predicted value of each policy. Each policy is a series of allowable actions in a vector U, where actions correspond to different state transitions (i.e., different Bπ,τ matrices) that can be chosen by the agent for each state factor. Policies are chosen by sampling from this distribution.</td>
<td>Allowable policies include the decision to:<br>1. Stay in the start state<br>2. Get the hint and then choose the left machine<br>3. Get the hint and then choose the right machine<br>4. Immediately choose the left machine (and then return to the start state)<br>5. Immediately choose the right machine (and then return to the start state)</td>
</tr>
<tr>
<td>A matrix: p(oτ|sτ)</td>
<td>A matrix encoding beliefs about the relationship between hidden states and observable outcomes at each time point τ (i.e., the probability that specific outcomes will be observed given specific hidden states at specific times). Note that in the POMDP structure typically used in the active inference literature (and which we describe in this tutorial), the likelihood is assumed to remain constant across time points in a trial, and hence will not differ at different values for τ (although one could adjust this if so desired). The likelihood is also assumed to be identical across policies, and so there is no indexing with respect to π.<br>When there is more than one outcome modality, there is one A matrix per outcome modality. When there is more than one state factor, these matrices become high-dimensional and are technically referred to as tensors. For example, a second state factor corresponds to a third matrix dimension, a third state factor corresponds to a fourth matrix dimension, and so forth.</td>
<td>Encodes beliefs about the relationship between:<br>1. Probability that the hint is accurate in each context<br>2. Probability of reward in each context<br>3. Identity mapping between choice states and observed behavior</td>
</tr>
<tr>
<td>Bπ,τ matrix: p(sτ+1|sτ, π)</td>
<td>A matrix encoding beliefs about how hidden states will evolve over time (transition probabilities). For states that are under the control of the agent, there are multiple Bπ,τ matrices, where each matrix corresponds to one action (state transition) that the agent may choose at a given time point (if consistent with an allowable policy). When there is more than one hidden state factor, there is one or more Bπ,τ matrices per state factor (depending on policies).</td>
<td>Encodes beliefs that:<br>1. Context does not change within a trial<br>2. Transitions from any choice state to any other are possible, depending on the policy.</td>
</tr>
<tr>
<td>C matrix: p(oτ|C)</td>
<td>A matrix encoding the degree to which some observed outcomes are preferred over others (technically modeled as prior expectations over outcomes). When there is more than one outcome modality, there is one C matrix per outcome modality. Rows indicate possible observations; columns indicate time points. Note that each column of values in C is passed through a softmax function (transforming it into a proper probability distribution) and then log-transformed (using the natural log). Thus, preferences become log-probabilities over outcomes.</td>
<td>Encodes the stronger preference for wins than losses. Wins are also more preferred at the second time point than the third time point.</td>
</tr>
</tbody>
</table>

---

## table_2 (p16) — Table 1 (continued). [3 cols × 2 rows]

- **Caption:** Table 1 (continued).
- **Notes:** Continuation of Table 1 from page 15. Footnote: *While, for consistency, we have used the standard notation found in the active inference literature, it is important to note that it does not always clearly distinguish between distributions and the possible values taken by random variables under those distributions. For example, π refers to the distribution over policies, but when used as a subscript it indexes each individual policy (e.g., Bπ,τ indicates a distinct matrix for each different policy). This same convention holds for s and o.
- **Verified:** true

| Model variable* | General definition | Model specification for explore–exploit task (described in detail Section 3) |
|---|---|---|
| D vector: p(s1) | A vector encoding beliefs about (a probability distribution over) initial hidden states. When there is more than one hidden state factor, there is one D vector per state factor. | The agent begins in an initial state of maximal uncertainty about the context state (prior to learning), but complete certainty that it will start in the ‘start’ choice state. |
| E vector: p(π) | A distribution encoding beliefs about what policies will be chosen a priori (a prior probability distribution over policies, implemented as a vector assigning one value to each policy), based on the number of times different actions have been chosen in the past. | The agent has no initial habits to choose one slot machine or another (prior to learning). |

---

## table_3 (p18) — Table 2 Matrix formulation of equations used for inference. [4 cols × 3 rows]

- **Caption:** Table 2 Matrix formulation of equations used for inference.
- **Notes:** Table continues on next page. Equations contain mathematical notation. B† denotes the transpose of B (dagger notation). Aᵀ denotes A-transpose. ½ denotes one-half.
- **Verified:** true

| Model update component | Update equation | Explanation | Model-specific description for explore–exploit task (described in detail Section 3) |
|---|---|---|---|
| Updating beliefs about initial states expected under each allowable policy. | επ,τ=1 ← ½(ln D + ln(B†π,τ sπ,τ+1)) + ln Aᵀoτ − ln sπ,τ=1 sπ,τ=1 = σ(½(ln D + ln(B†π,τ sπ,τ+1)) + ln Aᵀoτ) | First equation: The variable επ,τ=1 is the state prediction error with respect to the first time point in a trial. Minimizing this error corresponds to minimizing VFE (via gradient descent) and is used to update posterior beliefs over states. The term (ln D + ln(B†π,τ sπ,τ+1)) corresponds to prior beliefs in Bayesian inference, based on beliefs about the probability of initial states, D, and the probability of transitions to future states under a policy, ln(B†π,τ sπ,τ+1). The term Aᵀoτ corresponds to the likelihood term in Bayesian inference, evaluating how consistent observed outcomes are with each possible state. The term ln sπ,τ=1 corresponds to posterior beliefs over states (for the first time point in a trial) at the current update iteration. Second Equation: We move to the solution for the posterior sπ,τ=1 by setting επ,τ=1 = 0, solving for ln sπ,τ=1, and then taking the softmax (normalized exponential) function (denoted σ) to ensure that the posterior over states is a proper probability distribution with non-negative values that sums to 1. This equation is described in more detail in the main text. A numerical example of the softmax function is also shown in Appendix A. | Updating beliefs about: 1. Whether the left vs. right slot machine is more likely to pay out on a given trial. 2. The initial choice state (here, always the ‘start’ state). |
| Updating beliefs about all states after the first time point in a trial that are expected under each allowable policy. | επ,τ>1 ← ½(ln(Bπ,τ−1 sπ,τ−1) + ln(B†π,τ sπ,τ+1)) + ln Aᵀoτ − ln sπ,τ>1 sπ,τ>1 = σ(½(ln(Bπ,τ−1 sπ,τ−1) + ln(B†π,τ sπ,τ+1)) + ln Aᵀoτ) | First equation: The variable επ,τ>1 is the state prediction error with respect to all time points in a trial after the first time point. Minimizing this error corresponds to minimizing VFE (via gradient descent) and is used to update posterior beliefs over states. The term (ln(Bπ,τ−1 sπ,τ−1) + ln(B†π,τ sπ,τ+1)) corresponds to prior beliefs in Bayesian inference, based on beliefs about the probability of transitions from past states, ln(Bπ,τ−1 sπ,τ−1), and the probability of transitions to future states, ln(B†π,τ sπ,τ+1), under a policy. The term ln Aᵀoτ corresponds to the likelihood term in Bayesian inference, evaluating how consistent observed outcomes are with each possible state. Second Equation: As in the previous row, we move to the solution for the posterior, sπ,τ>1, by setting επ,τ>1 = 0, solving for ln sπ,τ>1, and then taking the softmax function (σ). This equation is described in more detail in the main text. | Updating beliefs about: 1. Whether the left vs. right slot machine is more likely to pay out on a given trial. 2. Beliefs about choice states after the initial time point (here, this depends on the choice to take the hint or to select one of the slot machines). |
| Probability of selecting each allowable policy | π0 = σ(ln E − γG) π = σ(ln E − F − γG) | The initial distribution over policies before making any observations (π0), and the posterior distribution over policies after an observation (π). The initial distribution is made up of the learned prior over policies encoded in the E vector (reflecting the number of times a policy has previously been chosen) and the expected free energy of each allowable policy (G). The posterior distribution is determined by E, G, and the variational free energy (F) under each policy after making a new observation. The influence of G is also modulated by an expected precision term (γ), which encodes prior confidence in beliefs about G (described further in the main text; also see Fig. 9). See row 1 for an explanation of the function of the σ symbol. We note, however, that incorporation of E, F, and/or γ when computing π is a modeling choice. These need not be included in all cases (e.g., see top-left portion of Fig. 5; also see Da Costa, Parr et al., 2020). In some contexts, one might choose to include some of these terms but not others, or to only include G. This depends on the research question. (e.g., E will be useful if task behavior is influenced by habits, while F/γ can be useful when there are many possible deep policies to choose from). See the row in this table on ‘Expected free energy precision’ for more details about inference over policies when F/γ are included. This is also discussed further in the main text. | Updating overall beliefs about whether the best course of action is to take the hint and/or to choose the left vs. right slot machine. |

---

## table_4 (p19) — Table 2 (continued). [4 cols × 2 rows]

- **Caption:** Table 2 (continued).
- **Notes:** Table continues on next page. Equations contain complex mathematical notation. B† denotes the transpose of B (dagger notation). Aᵀ denotes A-transpose. ½ denotes one-half. DKL denotes KL divergence. The rawtext has 'sightly' (apparent typo for 'slightly') matching the original PDF.
- **Verified:** true

<table>
<thead><tr>
<th>Model update component</th>
<th>Update equation</th>
<th>Explanation</th>
<th>Model-specific description for explore–exploit task (described in detail Section 3)</th>
</tr></thead>
<tbody>
<tr>
<td>Expected free energy of each allowable policy</td>
<td>Gπ = DKL [q(o|π) ∥ p(o|C)] + Eq(s|π) [H [p(o|s)]]<br>Gπ = ∑τ (Asπ,τ · (ln Asπ,τ − ln Cτ) − diag(Aᵀ ln A) · sπ,τ)</td>
<td>The first equation reproduces the ‘risk + ambiguity’ expression for the expected free energy of each policy (Gπ) that is explained in the main text. The second equation shows this same expression in terms of the elements in the POMDP model used in this tutorial (i.e., in matrix notation). Expected free energy evaluates the value of each policy based on their expected ability to: (1) generate the most desired outcomes, and (2) minimize uncertainty about hidden states. Achieving the most desired outcomes corresponds to minimizing the KL divergence between preferred observations, p(o|C) = Cτ, and the observations expected under each policy, q(o|π) = Asπ,τ = oπ,t. Minimizing uncertainty corresponds to minimizing the expected entropy of the likelihood (Eq(s|π) [H [p(o|s)]] = −diag(Aᵀ ln A) · sπ,τ). Note that the diag() function simply takes the diagonal elements of a matrix and places them in a row vector. This is simply a convenient method for extracting and operating on the correct matrix entries to calculate the entropy, H [p(o|s)] = −∑ p(o|s) ln p(o|s), of the distributions encoded within each column in A. For simple numerical examples of calculating the risk and ambiguity terms, see discussion of ‘outcome prediction errors’ in Section 2.4.</td>
<td>The ‘risk’ term – DKL [q(o|π) ∥ p(o|C)] = Asπ,τ · (ln Asπ,τ − ln Cτ) – drives the agent to select the slot machine expected to be most likely to pay out. If the value of winning money in Cτ is high enough (i.e., if p(o|C) is sufficiently precise), this will deter the agent from choosing to ask for the hint.<br>The ‘ambiguity’ term – Eq(s|π) [H [p(o|s)]] = −diag(Aᵀ ln A) · sπ,τ – drives the agent to minimize uncertainty by asking for the hint.</td>
</tr>
<tr>
<td>Marginal free energy of each allowable policy</td>
<td>Fπ = Eq(s|π) [ln q(s|π) − ½ Eq(sτ−1|π)[ln p(sτ|sτ−1, π)] − ½ Eq(sτ+1|π)[ln p(sτ|sτ+1, π)] − ln p(oτ|sτ)]<br>Fπ = ∑τ sπ,τ · (ln sπ,τ − ½(ln(Bπ,τ−1 sπ,τ−1) + ln(B†π,τ sπ,τ+1)) − ln Aᵀoτ)</td>
<td>The first equation shows the marginal (as opposed to variational) free energy, which is now used in the most recent implementations of active inference. The second equation shows this same expression in terms of the elements in the POMDP model used in this tutorial (i.e., in matrix notation). Marginal free energy has a sightly different form than the expressions for VFE that are also shown in the text (and which have been used in many previous papers in the active inference literature). This updated form improves on certain limitations of the message passing algorithms derived from minimization of VFE (see Section 2.3; also see (Parr, Markovic, Kiebel, &amp; Friston, 2019). Marginal free energy evaluates the evidence that inferred states provide for each policy (based on new observations at each time point). See the first two rows in this table on updating beliefs about states for an explanation of how each term in the equation relates to Bayesian inference.</td>
<td>This would encode the amount of surprise (given a choice of policy) when observing a hint or a win/loss after selecting a specific slot machine.</td>
</tr>
</tbody>
</table>

---

## table_5 (p20) — Table 2 (continued). [4 cols × 1 rows]

- **Caption:** Table 2 (continued).
- **Notes:** This is the final row of Table 2. Variable names from rawtext: π0 (pi-zero), Gerror, βupdate, β0 (beta-zero), ψ (psi). The gamma distribution symbol is Γ. Table note: The term B†π,τ denotes the transpose of Bπ,τ with normalized columns (i.e., columns that sum to 1). Note that you may commonly see the dot (·) notation used in the active inference literature to denote transposed matrix multiplication, such as A · oτ, which means Aᵀoτ (we use the latter notation here). When A matrices have more than two dimensions (i.e., when they are tensors), the transpose is applied to the two-dimensional matrix associated with each value of the other dimensions. The σ symbol indicates a softmax operation (for an introduction see Appendix A), which transforms vector values to make up a proper probability distribution (i.e., with non-negative values that sum to 1). Italicized variables indicate vectors (or single numbers [scalars] in the case of β and γ). Bold, non-italicized variables indicate matrices. Subscripts indicate conditional probabilities; e.g., sπ,τ = p(sτ|π).
- **Verified:** true

<table>
<thead><tr>
<th>Model update component</th>
<th>Update equation</th>
<th>Explanation</th>
<th>Model-specific description for explore–exploit task (described in detail Section 3)</th>
</tr></thead>
<tbody>
<tr>
<td>Expected free energy precision</td>
<td>p(γ) = Γ(1, β)<br>E[γ] = γ = 1/β<br>Iterated to convergence:<br>π0 ← σ(ln E − γG)<br>π ← σ(ln E − F − γG)<br>Gerror ← (π − π0) · (−G)<br>βupdate ← β − β0 + Gerror<br>β ← β − βupdate/ψ<br>γ ← 1/β</td>
<td>The β term, and its prior value β0, is a hyperparameter on the expected free energy precision term (γ). Specifically, β is the ‘rate’ parameter of a gamma distribution (Γ) with a ‘shape’ parameter value of 1. The expected value of this distribution, E[γ] = γ, is equal to the reciprocal of β. Note that we use the non-italicized γ to refer to the random variable and use the italicized γ to refer to the scalar value of that variable. This scalar is what is subsequently updated based on the equations shown here.<br>The γ term controls the precision of G, based on the agent’s confidence in its estimates of expected free energy. This confidence changes when new observations are consistent or inconsistent with G. More specifically, γ modulates the influence of G on policy selection based upon a G prediction error (Gerror). This is calculated based on the difference between the initial distribution over policies (π0) and the posterior distribution after making a new observation (π). The difference between these terms reflects the extent to which new observations (scored by F) make policies more or less likely. If the vector encoding the posterior over policies increases in magnitude in comparison to the prior, and still points in the same direction, the difference vector between the posterior and the prior will point in the same direction as the −G vector (i.e., less than a 90° angle apart; see Fig. 9). If so, the value of γ will increase, thereby increasing the impact of G on policy selection. In contrast, if the difference vector between the posterior and the prior does not point in the same direction as the −G vector (i.e., greater than a 90° angle apart), γ will decrease and thereby reduce the impact of G on policy selection (i.e., as the agent’s confidence in its estimates of expected free energy has decreased).<br>Note that the βupdate term mediating these updates technically corresponds to the gradient of free energy with respect to γ (∇γF). The subsequent update in the value of γ is such that G contributes to the posterior over policies in an optimal manner. β and Gerror are often discussed in relation to dopamine in the active inference literature.<br>Note that β0 is the initial prior (which is not updated), and β is the initial posterior, which is subsequently updated to provide a new estimate for γ = 1/β. The variable ψ is a step size parameter that reduces the magnitude of each update and promotes stable convergence to final values of γ. For a derivation of these equations, see Appendix in Sales, Friston, Jones, Pickering, and Moran (2019).</td>
<td>A higher value for β would reduce an agent’s confidence in the best policy based on the values in G. This might lead the agent to select a slot machine more randomly or based to a greater extent on its past choices (i.e., if it has a precise prior over policies in the vector E).</td>
</tr>
</tbody>
</table>

---

## table_6 (p30) — Table 3 Output fields for spm_MDP_VB_X_tutorial.m simulation script. [4 cols × 11 rows]

- **Caption:** Table 3 Output fields for spm_MDP_VB_X_tutorial.m simulation script.
- **Notes:** Table continues on next page. The table has 4 columns: MDP Field, Model Element, Structure, Description.
- **Verified:** true

<table>
<thead><tr>
<th>MDP Field</th>
<th>Model Element</th>
<th>Structure</th>
<th>Description</th>
</tr></thead>
<tbody>
<tr>
<td>MDP.F</td>
<td>Negative variational free energy of each policy over time.</td>
<td>Rows = policies.<br>Columns = time points.</td>
<td>Negative variational free energy of each policy at each time point in the trial. For example, if there are 2 policies and 6 time points there will be a 2 × 6 matrix containing the negative variational free energy of each policy at each point in the trial.</td>
</tr>
<tr>
<td>MDP.G</td>
<td>Negative expected free energy of each policy over time.</td>
<td>Rows = policies.<br>Columns = time points.</td>
<td>Negative expected free energy of each policy at each time point in the trial. For example, if there are 2 policies and 6 time points there will be a 2 × 6 matrix containing the negative expected free energy of each policy at each point in the trial.</td>
</tr>
<tr>
<td>MDP.H</td>
<td>Total negative variational free energy over time.</td>
<td>Columns = time points.</td>
<td>Total negative variational free energy averaged across states and policies at each time point. For example, if there are 8 time points there will be a 1 × 8 row vector containing the total negative free energy at each time point.</td>
</tr>
<tr>
<td>MDP.Fa<br>MDP.Fd<br>MDP.Fb<br>...</td>
<td>MDP.Fa is the negative free energy of parameter ‘a’ (if learning A matrix). There are also analogous fields if learning other matrices/vectors (e.g., MDP.Fd for learning the parameters of the D vector, etc.).</td>
<td>Columns = one per outcome modality or hidden state factor (i.e., depending on the specific parameters being learned). If the agent is learning parameters of a single vector (e.g., E), this will be a single column.</td>
<td>KL divergence between the parameters of the matrix/vector that is being learned at the beginning of each trial and at the end of each trial. Each column in the vector may represent an outcome modality (i.e., in the case of the A matrix), a hidden state factor (i.e., in the case of the B matrix and D vector), or any other vector (e.g., the E vector).</td>
</tr>
<tr>
<td>MDP.O</td>
<td>Outcome vectors.</td>
<td>Rows = outcome modalities.<br>Columns = time points.</td>
<td>Vectors (one per cell) specifying the outcomes for each modality at each time point. Observed outcomes are encoded as 1s, with 0s otherwise.</td>
</tr>
<tr>
<td>MDP.P</td>
<td>Probability of emitting an action.</td>
<td>Rows = one per controllable state factor.<br>Columns = actions.<br>Third dimension = time point.</td>
<td>The probability of emitting each particular action, expressed as a softmax function of a vector containing the probability of each action summed over each policy. For example, assume that there are two possible actions, with a posterior over policies of [.4 .4 .2], with policy 1 and 2 leading to action 1, and policy 3 leading to action 2. The probability of action 1 and 2 is therefore [.8 .2]. This vector is then passed through another softmax function controlled by the inverse temperature parameter α, which by default is extremely large (α = 512). Actions are then sampled from the resulting distribution, where higher α values promote more deterministic action selection (i.e., by choosing the action with the highest probability).</td>
</tr>
<tr>
<td>MDP.Q</td>
<td>Posteriors over states under each policy at the end of the trial.</td>
<td>1 cell per state factor.<br>Rows = states.<br>Columns = time points.<br>Third dimension = policy number.</td>
<td>Posterior probability of each state conditioned on each policy at the end of the trial after successive rounds of updating at each time point.</td>
</tr>
<tr>
<td>MDP.R</td>
<td>Posteriors over policies.</td>
<td>Rows = policies.<br>Columns = time points.</td>
<td>Posterior over policies at each time point.</td>
</tr>
<tr>
<td>MDP.X</td>
<td>Overall posteriors over states at the end of the trial. These are Bayesian model averages of the posteriors over states under each policy.</td>
<td>1 cell per state factor.<br>Rows = states.<br>Columns = time points.</td>
<td>This means taking a weighted average of the posteriors over states under each policy, where the weighting is determined by the posterior probability of each policy.</td>
</tr>
<tr>
<td>MDP.un</td>
<td>Neuronal encoding of policies.</td>
<td>1 cell per policy dimension.<br>Rows = policies.<br>Columns = iterations of message passing (16 per time point). For example, 16 iterations, and 8 time points gives a vector with 128 columns).</td>
<td>Simulated neuronal encoding of the posterior probability of each policy at each iteration of message passing.</td>
</tr>
<tr>
<td>MDP.vn</td>
<td>Neuronal encoding of state prediction errors.</td>
<td>1 cell per state factor.<br>Rows = iterations of message passing (16 per time point).<br>Columns = states.<br>Third Dimension: time point the belief is about (τ).<br>Fourth Dimension: time point the belief is at (t).</td>
<td>Bayesian model average of state prediction errors at each iteration of message passing (weighted by the posterior probability of the associated policies).</td>
</tr>
</tbody>
</table>

---

## table_7 (p31) — Table 3 (continued). [4 cols × 4 rows]

- **Caption:** Table 3 (continued).
- **Notes:** Continuation of Table 3 from page 30. Page bottom contains a footnote (partially visible): 'Constant α = 512...' with similar direction notation.
- **Verified:** true

<table>
<thead><tr>
<th>MDP Field</th>
<th>Model Element</th>
<th>Structure</th>
<th>Description</th>
</tr></thead>
<tbody>
<tr>
<td>MDP.xn</td>
<td>Neuronal encoding of hidden states.</td>
<td>1 cell per state factor.<br>Rows = iterations of message passing (16 per time point).<br>Columns = states.<br>Third Dimension: time point the belief is about (τ).<br>Fourth Dimension: time point the belief is at (t).</td>
<td>Bayesian model average of normalized firing rates, which reflect posteriors over states at each iteration of message passing (weighted by the posterior probability of the associated policies).</td>
</tr>
<tr>
<td>MDP.wn</td>
<td>Neuronal encoding of tonic dopamine, reflecting the current value of γ.</td>
<td>Rows = number of iterative updates (16 per time point). For example, if there were two time points in a trial this would be 1 column with 32 rows.</td>
<td>This reflects the value of the expected precision of the expected free energy over policies (γ) at each iteration of updating.</td>
</tr>
<tr>
<td>MDP.dn</td>
<td>Neuronal encoding of phasic dopamine responses, reflecting the rate of change in γ.</td>
<td>Rows = number of iterative updates (16 per time point). For example, if there were two time points in a trial this would be 1 column with 32 rows.</td>
<td>This variable reflects the rate of change in the expected precision of expected free energy over policies (γ) at each iteration of updating.</td>
</tr>
<tr>
<td>MDP.rt</td>
<td>Simulated reaction times.</td>
<td>Columns = time points.</td>
<td>Computation time (i.e., time to convergence) for each round of message passing and action selection.</td>
</tr>
</tbody>
</table>

---

## Review Checklist

- [ ] table_0 — artifact confirmed
- [ ] table_1 — 6 rows, 3 cols verified
- [ ] table_2 — 2 rows, 3 cols verified
- [ ] table_3 — 3 rows, 4 cols verified
- [ ] table_4 — 2 rows, 4 cols verified
- [ ] table_5 — 1 rows, 4 cols verified
- [ ] table_6 — 11 rows, 4 cols verified
- [ ] table_7 — 4 rows, 4 cols verified
