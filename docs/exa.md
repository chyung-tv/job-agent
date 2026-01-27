# Exa API Documentation Context

# Quickstart

> Make your first request to one of Exa's API endpoints

***

## Create and setup your API key

<Card title="Get your Exa API key" icon="key" horizontal href="https://dashboard.exa.ai/api-keys" />

<br />

## Create a .env file

Create a file called `.env` in the root of your project and add the following line.

```bash  theme={null}
EXA_API_KEY=your api key without quotes
```

<br />

{" "}

## Make an API request

Use our python or javascript SDKs, or call the API directly with cURL.

<Tabs>
  <Tab title="Python">
    Install the python SDKs with pip.  If you want to store your API key in a `.env` file, make sure to install the dotenv library.

    ```bash  theme={null}
    pip install exa-py
    pip install openai
    pip install python-dotenv
    ```

    Once you've installed the SDKs, create a file called `exa.py` and add the code below.

    <Tabs>
      <Tab title="Search and crawl">
        Get a list of results and their full text content.

        ```python python theme={null}
        from exa_py import Exa
        from dotenv import load_dotenv

        import os

        # Use .env to store your API key or paste it directly into the code
        load_dotenv()
        exa = Exa(os.getenv('EXA_API_KEY'))

        result = exa.search_and_contents(
          "An article about the state of AGI",
          type="auto",
          text=True,
        )

        print(result)
        ```
      </Tab>

      <Tab title="Answer">
        Get an answer to a question, grounded by citations from exa.

        ```python python theme={null}
        from exa_py import Exa
        from dotenv import load_dotenv

        import os

        # Use .env to store your API key or paste it directly into the code
        load_dotenv()
        exa = Exa(os.getenv('EXA_API_KEY'))

        result = exa.stream_answer(
          "What are the latest findings on gut microbiome's influence on mental health?",
          text=True,
        )

        for chunk in result:
          print(chunk, end='', flush=True)
        ```
      </Tab>

      <Tab title="Chat Completions">
        Get a chat completion from exa.

        ```python python theme={null}
        from openai import OpenAI
        from dotenv import load_dotenv

        import os

        # Use .env to store your API key or paste it directly into the code
        load_dotenv()

        client = OpenAI(
          base_url="https://api.exa.ai",
          api_key=os.getenv('EXA_API_KEY'),
        )

        completion = client.chat.completions.create(
          model="exa",
          messages = [
          {"role": "system", "content": "You are a helpful assistant."},
          {"role": "user", "content": "What are the latest developments in quantum computing?"}
        ],

          extra_body={
            "text": True
          }
        )
        print(completion.choices[0].message.content)
        ```
      </Tab>

      <Tab title="Find similar links and get full text">
        Find similar links to a given URL and get the full text for each link.

        ```python python theme={null}
        from exa_py import Exa
        from dotenv import load_dotenv

        import os

        load_dotenv()

        exa = Exa(os.getenv('EXA_API_KEY'))

        # get similar links to this post about AGI
        result = exa.find_similar(
          "https://amistrongeryet.substack.com/p/are-we-on-the-brink-of-agi",
          exclude_domains = ["amistrongeryet.substack.com"],
          num_results = 3
        )
        urls = [link_data.url for link_data in result.results]

        # get full text for each url
        web_pages = exa.get_contents(
          urls,
          text=True
        )

        for web_page in web_pages.results:
          print(f"URL: {web_page.url}")
          print(f"Text snippet: {web_page.text[:500]} ...")
          print("-"*100)
        ```
      </Tab>
    </Tabs>
  </Tab>

  <Tab title="JavaScript">
    Install the javascript SDK with npm. If you want to store your API key in a `.env` file, make sure to install the dotenv library.

    ```bash  theme={null}
    npm install exa-js
    npm install openai
    npm install dotenv
    ```

    Once you've installed the SDK, create a file called `exa.ts` and add the code below.

    <Tabs>
      <Tab title="Search and crawl">
        Get a list of results and their full text content.

        ```javascript javascript theme={null}
        import dotenv from 'dotenv';
        import Exa from 'exa-js';

        dotenv.config();

        const exa = new Exa(process.env.EXA_API_KEY);

        const result = await exa.searchAndContents(
          "An article about the state of AGI",
          {
            type: "auto",
            text: true
          }
        );

        // print the first result
        console.log(result.results[0]);
        ```
      </Tab>

      <Tab title="Answer">
        Get an answer to a question, grounded by citations from exa.

        ```javascript javascript theme={null}
        import dotenv from 'dotenv';
        import Exa from 'exa-js';

        dotenv.config();

        const exa = new Exa(process.env.EXA_API_KEY);
        for await (const chunk of exa.streamAnswer(
          "What is the population of New York City?",
          {
            text: true
          }
        )) {
          if (chunk.content) {
            process.stdout.write(chunk.content);
          }
          if (chunk.citations) {
            console.log("\nCitations:", chunk.citations);
          }
        }
        ```
      </Tab>

      <Tab title="Chat Completions">
        Get a chat completion from exa.

        ```javascript javascript theme={null}
        import OpenAI from "openai";
        import dotenv from 'dotenv';
        import Exa from 'exa-js';

        dotenv.config();

        const openai = new OpenAI({
          baseURL: "https://api.exa.ai",
          apiKey: process.env.EXA_API_KEY,
        });

        async function main() {
        const completion = await openai.chat.completions.create({
          model: "exa",
          messages: [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What are the latest developments in quantum computing?"}
          ],
          store: true,
          stream: true,
          extra_body: {
            text: true // include full text from sources
          }
        });

        for await (const chunk of completion) {
          console.log(chunk.choices[0].delta.content);
          }
        }

        main();
        ```
      </Tab>

      <Tab title="Find similar links and get full text">
        Find similar links to a given URL and get the full text for each link.

        ```javascript javascript theme={null}
        import Exa from 'exa-js';
        import dotenv from 'dotenv';

        dotenv.config();

        const exa = new Exa(process.env.EXA_API_KEY);

        // Find similar links to this post about AGI
        const result = await exa.findSimilar(
          "https://amistrongeryet.substack.com/p/are-we-on-the-brink-of-agi",
          {
            excludeDomains: ["amistrongeryet.substack.com"],
            numResults: 3
          }
        );

        const urls = result.results.map(linkData => linkData.url);

        // Get full text for each URL
        const webPages = await exa.getContents(urls, { text: true });

        webPages.results.forEach(webPage => {
          console.log(`URL: ${webPage.url}`);
          console.log(`Text snippet: ${webPage.text.slice(0, 500)} ...`);
          console.log("-".repeat(100));
        });
        ```
      </Tab>
    </Tabs>
  </Tab>

  <Tab title="cURL">
    Pass one of the following commands to your terminal to make an API request.

    <Tabs>
      <Tab title="Search and crawl">
        Get a list of results and their full text content.

        ```bash bash theme={null}
        curl --request POST \
            --url https://api.exa.ai/search \
            --header 'accept: application/json' \
            --header 'content-type: application/json' \
            --header "x-api-key: ${EXA_API_KEY}" \
            --data '
        {
            "query": "An article about the state of AGI",
            "type": "auto",
            "contents": {
              "text": true
            }
        }'
        ```
      </Tab>

      <Tab title="Answer">
        Get an answer to a question, grounded by citations from exa.

        ```bash bash theme={null}
        curl --request POST \
          --url https://api.exa.ai/answer \
          --header 'accept: application/json' \
          --header 'content-type: application/json' \
          --header "x-api-key: ${EXA_API_KEY}" \
          --data "{
            \"query\": \"What are the latest findings on gut microbiome's influence on mental health?\",
            \"text\": true
          }"
        ```
      </Tab>

      <Tab title="Chat Completions">
        Get a chat completion from exa.

        ```bash bash theme={null}
        curl https://api.exa.ai/chat/completions \
          -H "Content-Type: application/json" \
          -H "x-api-key: ${EXA_API_KEY}" \
          -d '{
            "model": "exa", 
            "messages": [
              {
                "role": "system",
                "content": "You are a helpful assistant."
              },
              {
                "role": "user",
                "content": "What are the latest developments in quantum computing?"
              }
            ],
            "extra_body": {
              "text": true
            }
          }'
        ```
      </Tab>
    </Tabs>
  </Tab>
</Tabs>


---

> To find navigation and other pages in this documentation, fetch the llms.txt file at: https://exa.ai/docs/llms.txt

# Answer

> Get an LLM answer to a question informed by Exa search results. `/answer` performs an Exa search and uses an LLM to generate either:
1. A direct answer for specific queries. (i.e. "What is the capital of France?" would return "Paris")
2. A detailed summary with citations for open-ended queries (i.e. "What is the state of ai in healthcare?" would return a summary with citations to relevant sources)

The response includes both the generated answer and the sources used to create it. The endpoint also supports streaming (as `stream=True`), which will return tokens as they are generated.

Alternatively, you can use the OpenAI compatible [chat completions interface](https://docs.exa.ai/reference/chat-completions#answer).


<Card title="Get your Exa API key" icon="key" horizontal href="https://dashboard.exa.ai/api-keys" />

<Info>
  Need custom output formats or specialized behavior from `/answer`? Reach out to [hello@exa.ai](mailto:hello@exa.ai) and we can help tailor the endpoint to your use case.
</Info>

