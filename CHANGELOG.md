# CHANGELOG

<!-- version list -->

## v1.12.0 (2026-06-16)

### Features

- **optimizer**: Add metric rubric to optimizer prompt
  ([`92806bf`](https://github.com/nachollorca/promptuna/commit/92806bfa33a1ec79fe82865f93612c18b889ae2a))

- **optimizer**: Show the scaffold and output schema of the program to the optimizer LM
  ([`71b060e`](https://github.com/nachollorca/promptuna/commit/71b060e2de09501dc6bdb0b4d4e500668fbdf3ee))


## v1.11.0 (2026-06-15)

### Features

- **program**: Add dataset loader
  ([`b07f44f`](https://github.com/nachollorca/promptuna/commit/b07f44f31f306748f0e42cf811aac96c6720645e))

### Refactoring

- **loader**: Move to its own module
  ([`f8f360d`](https://github.com/nachollorca/promptuna/commit/f8f360dab9c7d79c2d5ab374114fa08b2fef4a6b))


## v1.10.0 (2026-06-15)

### Documentation

- Add inspo and math to readme
  ([`d75fd0f`](https://github.com/nachollorca/promptuna/commit/d75fd0fee6fdc4fa99c2a2ba3c2fac8c720646a9))

- Remove comment that had been cleared out
  ([`2bf837d`](https://github.com/nachollorca/promptuna/commit/2bf837d6214f6f119a39b81cf257f77b7a4b24c5))

- Remove the pedantic mathy
  ([`ae850c1`](https://github.com/nachollorca/promptuna/commit/ae850c1b9b80bdb8256e456f3b9ec8201bf2db5a))

- Trim redundant docstrings
  ([`ba0d109`](https://github.com/nachollorca/promptuna/commit/ba0d109d02aa0e587561b6376b02cbeec589724b))

- **readme**: Add silly diagram for improvement loop
  ([`aee1dee`](https://github.com/nachollorca/promptuna/commit/aee1dee47bb7cb908ebbd9a73c261700d06b09f3))

### Features

- Edit readme but call it feat to trigger first pypi release
  ([`4ef14cc`](https://github.com/nachollorca/promptuna/commit/4ef14cc70ea8ae8ae891fe33202bc396c629082a))

### Refactoring

- Rename lmeh to promptuna
  ([`d0b44be`](https://github.com/nachollorca/promptuna/commit/d0b44be184701069486056196310a97da7b40efa))

- Reorganize the layout
  ([`ba8229d`](https://github.com/nachollorca/promptuna/commit/ba8229de96bfa90e603533528207991185a0e985))

### Testing

- Draft test suite
  ([`9f970bd`](https://github.com/nachollorca/promptuna/commit/9f970bde5006bf6b73864be095133046527f15c6))


## v1.9.0 (2026-06-12)

### Documentation

- **readme**: Explain briefly the concepts behind the optimization
  ([`08c3557`](https://github.com/nachollorca/promptuna/commit/08c35574aaf9d473a96c3b0068eadbec3ddc75bf))

### Features

- **optimizer**: Implement attentive reasoning queries
  ([`89f81a8`](https://github.com/nachollorca/promptuna/commit/89f81a8d7dd14cdd6963fcb2678d58892a2d3014))


## v1.8.0 (2026-06-12)

### Documentation

- **notebook**: Add a summary story of what we are doing
  ([`d4e1d24`](https://github.com/nachollorca/promptuna/commit/d4e1d24f653b08556f326d0c8af6d20efc3a2d52))

### Features

- **optimizer**: Stop propser early if the score is already perfect
  ([`c60741a`](https://github.com/nachollorca/promptuna/commit/c60741a43642702a405a45b4ad2564738477f38a))

### Refactoring

- **prompts**: Move prompts to jinja files instead of inlining them in the code
  ([`2301ca3`](https://github.com/nachollorca/promptuna/commit/2301ca3f21e7659eaccb12bb2e72db9a7ba61a54))


## v1.7.1 (2026-06-12)

### Bug Fixes

- **optimizer**: Ensure that jinja variables in nested prompt templates are shown properly
  ([`075dfa2`](https://github.com/nachollorca/promptuna/commit/075dfa26ab95599edc08f0aa80b715f3a597a65d))

- **optimizer**: Split the rendering of the results legend to avoid duplication in each step render
  ([`0a421ca`](https://github.com/nachollorca/promptuna/commit/0a421ca816556f878cc0e0d821d6982250af03a3))

### Refactoring

- **optimizer**: Move rendering code together instead of having reporting + optimizer
  ([`aa12d0f`](https://github.com/nachollorca/promptuna/commit/aa12d0f2d976faebf4b32566447f30883fce4491))


## v1.7.0 (2026-06-10)

### Code Style

- Little comments and style changes
  ([`e9308dc`](https://github.com/nachollorca/promptuna/commit/e9308dc470b1dd60c98edddeca266d0509638d31))

- Remove keyword-only separators
  ([`4d4ad62`](https://github.com/nachollorca/promptuna/commit/4d4ad62aa4cf9000af575703031fd88b1b95313b))

- **optimizer**: Use alias for nested output types
  ([`485c875`](https://github.com/nachollorca/promptuna/commit/485c875d57a77546e4ac2426b29d5dac90a50b67))

### Continuous Integration

- **gitignore**: Ignore notebooks
  ([`56ccecd`](https://github.com/nachollorca/promptuna/commit/56ccecd90fb2558849d92b50d8617b25b2bdf6bb))

### Documentation

- Clear up readme
  ([`5eefbdb`](https://github.com/nachollorca/promptuna/commit/5eefbdbfd90041aeed077883ba6cdeb3f5898192))

- **notebook**: Add optimization example
  ([`7bed3dc`](https://github.com/nachollorca/promptuna/commit/7bed3dc0a586dabf779ce012c82cb39e6f31f579))

- **notebook**: Add telemetry to the notebook
  ([`4f50ede`](https://github.com/nachollorca/promptuna/commit/4f50ede605773236820388a86c5e342e124b537b))

- **notebook**: Make the getting started notebook a first class citizen, use jupyter instead of
  marimo
  ([`f3cacf2`](https://github.com/nachollorca/promptuna/commit/f3cacf2b5bea6dce00f90ca699e5dbce83a7f057))

- **notebook**: Replace marimo with ipynb because we can render it in github
  ([`8882591`](https://github.com/nachollorca/promptuna/commit/88825919474565624c7eecc5a879dc3bfe0f0d51))

### Features

- Actually do the largest part of the implementation
  ([`fee6808`](https://github.com/nachollorca/promptuna/commit/fee68084119490610fc98c533aa4a407e36fdfc9))

- **optimizer**: Write initial sketch
  ([`2e2633f`](https://github.com/nachollorca/promptuna/commit/2e2633f241149a4c9074e3cca4cacf6ecf676379))

### Refactoring

- **datatypes**: Remove Dataset alias because it was misleading
  ([`f1fdec7`](https://github.com/nachollorca/promptuna/commit/f1fdec777c1083aa3912d1ab4d4a96d824a040fc))

- **optimizer**: Reduce cyclomatic complexity
  ([`0213f7f`](https://github.com/nachollorca/promptuna/commit/0213f7fa9b0567d00b06a74bc3debb74c25ecaee))


## v1.6.0 (2026-05-24)

### Features

- Add dispersion aggregates in RunResults
  ([`4f8117e`](https://github.com/nachollorca/promptuna/commit/4f8117e89a21ab4b38517c461c69166d17b698e2))


## v1.5.0 (2026-05-23)

### Documentation

- Make a better getting_started notebook
  ([`ae0c5ea`](https://github.com/nachollorca/promptuna/commit/ae0c5eaf080ee5bc0909465c68d39c2463007c57))

### Features

- Add repetition and aggregation in every stochastic touch
  ([`d594478`](https://github.com/nachollorca/promptuna/commit/d5944783a013616ee8fd813ed9992257ab6c5783))

### Refactoring

- Extract helpers for the thread processor to reduce cyclomatic complexity
  ([`6c1c15d`](https://github.com/nachollorca/promptuna/commit/6c1c15d3f72edc42e408404696e74a1e75950b68))

- Remove `OutputSchema` from `LMConfig`, it is now only responsibility of the target function
  ([`7b97e04`](https://github.com/nachollorca/promptuna/commit/7b97e049dcf530d1f4ff97a8312ae71958eed7e6))

- Split RawScore from Score to keep contracts honest
  ([`e260f0b`](https://github.com/nachollorca/promptuna/commit/e260f0b70a6656d09d87e3e948035c087d4326bf))


## v1.4.0 (2026-05-19)

### Features

- **datatypes**: Remove TargetOutput because now lmdk can natively observe requests / responses when
  complete is called
  ([`69cfef5`](https://github.com/nachollorca/promptuna/commit/69cfef53931aaa2f18c07e458037e0fd640636fa))


## v1.3.0 (2026-05-18)

### Continuous Integration

- Ignore notes
  ([`66103a4`](https://github.com/nachollorca/promptuna/commit/66103a49cec203dddf46fc5e41077d86083db3b5))

### Documentation

- Run a full experiment on the getting started notebook
  ([`a7b7991`](https://github.com/nachollorca/promptuna/commit/a7b79914406162c76670b8f90a3d14e81cf4fe62))

### Features

- **reporting**: Make a markdown report of the run results
  ([`27fb561`](https://github.com/nachollorca/promptuna/commit/27fb561c58197cca4e91fa3c22053d139c23f9a7))

### Refactoring

- **metrics-and-config**: Split into LLMJudge and ProgramaticMetric, get prompt_template out of
  Config, unify TargetConfig and JudgeConfig
  ([`3075799`](https://github.com/nachollorca/promptuna/commit/30757993422bf63fee153fc553087e1d6eff70a5))


## v1.2.0 (2026-05-18)

### Documentation

- **cookbook**: Add initial draft notebook
  ([`19725e6`](https://github.com/nachollorca/promptuna/commit/19725e6c33567134d34d2257cab4d32f30c05040))

- **cookbook**: Include ipynotebooks
  ([`d82a789`](https://github.com/nachollorca/promptuna/commit/d82a7897c3f234090639e58c47b7fcc136a53ed8))

- **readme**: Add execution section
  ([`7da8d50`](https://github.com/nachollorca/promptuna/commit/7da8d5096e0a1f79d5a9f9af08d86b1cf58801f4))

### Features

- **jugdge**: Create a default LLM judge
  ([`ddff7f3`](https://github.com/nachollorca/promptuna/commit/ddff7f38bfddd54b38d1069be8eeb017acb4cea0))


## v1.1.0 (2026-05-17)

### Bug Fixes

- Point what TargetFunction does, and what is it expected to return
  ([`5533753`](https://github.com/nachollorca/promptuna/commit/55337530ce5e8b00009539238e0225eff69adc21))

### Code Style

- Reorder the datatypes module
  ([`13db39e`](https://github.com/nachollorca/promptuna/commit/13db39e6b034d69de93faadca7529d9790607472))

### Continuous Integration

- **execution**: Fix type hinting with casts
  ([`c46e66e`](https://github.com/nachollorca/promptuna/commit/c46e66ec543c2ff286b1c617e0077ba63b0d9e38))

- **init**: Make a module-level init so the package actually works
  ([`78269b9`](https://github.com/nachollorca/promptuna/commit/78269b9c8ed3468fb746a87b583ed48083483bec))

### Documentation

- Clarify failure rate and rendered prompt
  ([`1cd87fc`](https://github.com/nachollorca/promptuna/commit/1cd87fcaf5d18b1c8868534542e2adea5e184fad))

- Fix mermaid
  ([`a479ff8`](https://github.com/nachollorca/promptuna/commit/a479ff830e7929ea9eb2abedafc244ea9012d9c4))

- Log the action plan
  ([`1f27dbc`](https://github.com/nachollorca/promptuna/commit/1f27dbc5cfdc87813b315b49b55e799cff98d2b5))

- Minor adjustments to readme
  ([`d6a230a`](https://github.com/nachollorca/promptuna/commit/d6a230abe48dcd12adc87c1c42598c24540f79e5))

- Remove dated TODO
  ([`fc56da4`](https://github.com/nachollorca/promptuna/commit/fc56da44abbeaebc0c5bec2b5c6cefc682a7923e))

- Remove PLAN
  ([`4f59af5`](https://github.com/nachollorca/promptuna/commit/4f59af5603df327050e17830c76f57f669f6dcde))

- Some more alignment
  ([`83dd38e`](https://github.com/nachollorca/promptuna/commit/83dd38e8ddf907037cdeca90f3a7bf7d686bcd35))

- Split between spec and TODO
  ([`214a3cb`](https://github.com/nachollorca/promptuna/commit/214a3cb2ee5b40a36197d761207c30c1a6724c5e))

- Try to make sense of the full story
  ([`9a41f89`](https://github.com/nachollorca/promptuna/commit/9a41f8901580a933faff95f955652e4ffcb515c4))

### Features

- First implementation for execution
  ([`0763d9f`](https://github.com/nachollorca/promptuna/commit/0763d9f602d2a981f0ec32233fe8ac475df18ec3))

### Refactoring

- Change namings once again
  ([`6233746`](https://github.com/nachollorca/promptuna/commit/62337468690c93bdb8e1027b527ab6f8df75fe28))

- Dismiss datasets where some examples have references and some have not
  ([`f997b18`](https://github.com/nachollorca/promptuna/commit/f997b1828383f84a6ddf690c3fbd7cae2bae6756))

- Fix hint errors
  ([`b143e2d`](https://github.com/nachollorca/promptuna/commit/b143e2d7fe377fecb7e29b44192a196776773746))

- Store successes and errors separately for trials and scorings
  ([`9338d6a`](https://github.com/nachollorca/promptuna/commit/9338d6abc0b91d914c0ee822a5b79c772a138e54))

### Testing

- Upload an example of the doubt I have
  ([`2c34b30`](https://github.com/nachollorca/promptuna/commit/2c34b308b5c511080b2fb94f2a9a473da74befb5))


## v1.0.0 (2026-05-03)

- Initial Release
