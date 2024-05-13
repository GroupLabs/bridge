import { PlaywrightCrawler, Dataset } from 'crawlee';

async function loginToLinkedIn(page) {
    await page.goto('https://www.linkedin.com/login');
    await page.waitForSelector('input[name="session_key"]'); // Email input
    await page.type('input[name="session_key"]', 'noelfranthomas@gmail.com'); // Replace with your email
    await page.waitForSelector('input[name="session_password"]'); // Password input
    await page.type('input[name="session_password"]', 'Nftnft2001.'); // Replace with your password
    await page.click('button[type="submit"]'); // Click login button
    await page.waitForNavigation(); // Wait for page navigation to confirm login
}

const handleSearchPage = async ({ page, request, enqueueLinks, searchQuery }) => {
    await loginToLinkedIn(page); // Login first if on login page


    // Navigate to homepage and use the search box
    await page.goto('https://www.linkedin.com/feed/');
    await page.waitForSelector('input[aria-label="Search"]'); // Wait for the search box
    await page.type('input[aria-label="Search"]', searchQuery); // Type the search query
    await page.keyboard.press('Enter'); // Press enter to start the search
    await page.waitForNavigation(); // Wait for the search results page to load

    // Click the "People" button to filter results to only show people
    await page.waitForSelector('button.artdeco-pill--choice');

    // Use page.evaluate to find and click the button by its text content
    await page.evaluate(() => {
        const buttons = Array.from(document.querySelectorAll('button.artdeco-pill--choice'));
        const peopleButton = buttons.find(button => button.textContent.includes('People'));
        if (peopleButton) {
            peopleButton.click();
        }
    });

    await page.waitForSelector('.search-results-container'); // Wait for the search results to update to "People" only
    const profileLinks = await page.evaluate(() => {
        const links = [];
        document.querySelectorAll('ul.reusable-search__entity-result-list a.app-aware-link').forEach(link => {
            const href = link.getAttribute('href');
            if (href && href.includes('/in/')) { // Ensure it's a profile link, not other links
                links.push(href);
            }
        });
        return links;
    });

    for (const link of profileLinks) {
        await enqueueLinks({
            urls: [link],
            userData: { label: 'PROFILE' }
        });
        await new Promise(resolve => setTimeout(resolve, 1000)); // Delay after enqueuing each link
    }

    // // Try navigating to the next page
    // const hasNextPage = await navigateToNextPage(page);
    // if (hasNextPage) {
    //     console.log("Ready to process the next page of results.");
    //     // Optionally call some function to handle the next page or repeat the current function
    // } else {
    //     console.log("No more pages or an error occurred.");
    // }
};

const handleProfilePage = async ({ page, request, enqueueLinks }) => {
    await new Promise(resolve => setTimeout(resolve, 1000)); // Delay to observe the page

    // Extract the first page details
    const details = await extractDetails(page);

    await Dataset.pushData(details);
};

// Function to extract details
async function extractDetails(page) {
    return page.evaluate(() => {
        const experienceBlocks = Array.from(document.querySelectorAll('div[data-view-name="profile-component-entity"]'));
        const experiences = experienceBlocks.map(block => {
            const roleTitle = block.querySelector('span[aria-hidden="true"]')?.innerText.trim();
            const companyDetails = block.querySelector('span.t-14.t-normal')?.innerText.trim();
            return { roleTitle, companyDetails };
        });
        return {
            url: document.location.href,
            name: document.querySelector('h1.text-heading-xlarge.inline.t-24.v-align-middle.break-words')?.innerText,
            location: document.querySelector('div.text-body-small.inline.t-black--light.break-words')?.innerText,
            headline: document.querySelector('div.text-body-medium.break-words')?.innerText,
            experiences
        };
    });
}

async function navigateToNextPage(page) {
    const nextButtonSelector = 'button.artdeco-pagination__button--next:not([disabled])'; // Ensure the button is not disabled
    const nextButton = await page.$(nextButtonSelector);
    if (nextButton) {
        await nextButton.click();
        await page.waitForNavigation({ waitUntil: 'networkidle0' });
        // Check if navigated to login after clicking next
        if (page.url().includes('linkedin.com/login')) {
            await loginToLinkedIn(page);
        }
        return true;
    } else {
        console.log("No more pages to navigate.");
        return false;
    }
}

const startCrawling = async (searchQuery) => {
    const crawler = new PlaywrightCrawler({
        headless: false,
        launchContext: {
            useIncognitoPages: false, // Set to false since we need cookies to persist for login session
            launchOptions: {
                slowMo: 250,
            },
        },
        requestHandler: async ({ request, ...rest }) => {
            if (request.userData.label === 'PROFILE') {
                await handleProfilePage({ request, ...rest });
            } else {
                await handleSearchPage({ request, ...rest, searchQuery });
            }
        },
    });

    crawler.run([
        'https://www.linkedin.com/feed/' // This is the starting URL
    ]);
};

// Retrieve the command-line argument for the search query
const searchQuery = process.argv[2];  // Assumes the search query is the first argument after the file name

if (!searchQuery) {
    console.error("Please provide a search query as a command-line argument.");
    process.exit(1);
}

startCrawling(searchQuery);