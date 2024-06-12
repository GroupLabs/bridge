import { PlaywrightCrawler, Dataset } from 'crawlee';

const handleGoogleSearchPage = async ({ page, request, enqueueLinks, searchQuery }) => {
    // Use the search query directly, since it's already encoded
    // const searchUrl = `https://www.google.com/search?q=${searchQuery}`;

    // await page.goto(searchUrl);
    await page.waitForSelector('div.g'); // Wait for search results to load

    let previousHeight;
    while (true) { // Infinite loop to handle infinite scrolling
        // Extract links and descriptions from the search results, filter out ads
        const results = await page.evaluate(() => {
            const items = [];
            const elements = document.querySelectorAll('div.g');
            elements.forEach((element) => {
                if (!element.querySelector('div[data-text-ad]')) { // Check if the result is not a sponsored ad
                    const titleElement = element.querySelector('h3');
                    const linkElement = element.querySelector('a');
                    const descriptionElement = element.querySelector('div.VwiC3b');
                    if (linkElement && descriptionElement) {
                        items.push({
                            url: linkElement.href,
                            title: titleElement ? titleElement.innerText : '',
                            description: descriptionElement.innerText
                        });
                    }
                }
            });
            return items;
        });

        // Store the extracted data
        await Dataset.pushData(results);

        // Scroll down to the bottom of the page
        previousHeight = await page.evaluate('document.body.scrollHeight');
        await page.evaluate('window.scrollTo(0, document.body.scrollHeight)');
        await page.waitForFunction(`document.body.scrollHeight > ${previousHeight}`);
        await page.waitForTimeout(2000); // Wait for the page to load more results

        // Check if new results have loaded by comparing the scroll height before and after
        const currentHeight = await page.evaluate('document.body.scrollHeight');
        if (previousHeight === currentHeight) {
            break; // If height didn't change, we've reached the bottom
        }
    }
};

const startCrawling = async (searchQuery) => {
    const crawler = new PlaywrightCrawler({
        headless: true,
        launchContext: {
            useIncognitoPages: true,
            launchOptions: {
                slowMo: 750,
            },
        },
        requestHandler: async ({ request, ...rest }) => {
            await handleGoogleSearchPage({ request, ...rest, searchQuery });
        },
    });

    await crawler.run([`https://www.google.com/search?q=${searchQuery}`]); // This is the starting URL
};

// Retrieve the command-line argument for the search query
const searchQuery = process.argv[2];  // Assumes the search query is the first argument after the file name

if (!searchQuery) {
    console.error("Please provide a search query as a command-line argument.");
    process.exit(1);
}

startCrawling(searchQuery);